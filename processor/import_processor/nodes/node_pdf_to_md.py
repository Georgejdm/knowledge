# processor/import_processor/nodes/node_pdf_to_md.py
import json
import shutil
import time
import zipfile
from pathlib import Path

import requests
from openai.types.beta.threads import message

from processor.import_processor.base import BaseNode, setup_logging
from processor.import_processor.exceptions import StateFieldError, FileProcessingError, ConfigurationError, \
    PdfConversionError
from processor.import_processor.state import ImportGraphState


class NodePDFToMD(BaseNode):
    """
    PDF 转 Markdown 节点：PDF结构化解析
    """

    name = "node_pdf_to_md"
    
    def _step_1_validate_paths(self, state: ImportGraphState):
        """
        步骤1：校验PDF文件路径和输出目录
        核心职责：参数非空校验 | 路径转换 | PDF文件有效性校验 | 输出目录自动创建
        返回：合法的PDF文件Path对象、输出目录Path对象
        异常：ValueError(参数缺失)、FileNotFoundError(文件无效)
        """
        #1.参数的非空校验
        pdf_path = state.get("pdf_path")
        if not pdf_path:
            raise StateFieldError(
                field_name="pdf_path",
                message="文件路径不能为空",
                expected_type=str
            )
        file_dir = state.get("file_dir")
        if not file_dir:
            raise StateFieldError(
                field_name="file_dir",
                message="输出路径不能为空",
                expected_type=str
            )
        #2.转换为Path对象
        pdf_path_obj = Path(pdf_path)
        file_dir_obj = Path(file_dir)

        #3.判断pdf是否存在
        if not pdf_path_obj.exists():
            raise FileProcessingError(f"文件{pdf_path_obj.name}不存在")

        #输出目录不存在则创建文件
        if not file_dir_obj.exists():
            self.logger.info(f"输出目录{file_dir_obj.name}不存在,执行创建命令")
            file_dir_obj.mkdir(parents=True,exist_ok=True)

        return pdf_path_obj, file_dir_obj

    def _step_2_upload_and_poll(self, pdf_path_obj: Path):
        """
        步骤2：上传PDF至MinerU并轮询解析任务状态
        核心流程：配置校验 → 获取上传链接 → 文件上传 → 任务轮询（直至完成/失败/超时）
        参数：pdf_path_obj-已校验的PDF Path对象
        返回：解析结果ZIP包下载链接full_zip_url
        异常：ValueError(配置缺失)、RuntimeError(请求/上传失败)、TimeoutError(任务超时)
        """

        #1.配置文件的校验
        if not self.config.mineru_base_url:
            raise ConfigurationError(
                "MinerU配置缺失：请在.env文件中正确配置 MINERU_BASE_URL 参数"
            )
        if not self.config.mineru_api_token:
            raise ConfigurationError(
                "MinerU配置缺失：请在.env文件中正确配置 MINERU_API_TOKEN 参数"
            )
        token = self.config.mineru_api_token
        url = f"{self.config.mineru_base_url}/file-urls/batch"
        header = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
        data = {
            "files": [
                {"name": f"{pdf_path_obj.name}"}
            ],
            "model_version": "vlm"
        }
        #发送请求
        response = requests.post(url, headers=header, json=data)
        if response.status_code != 200:
            raise PdfConversionError(
                '获取上传链接请求失败. 响应状态:{} ,响应信息:{}'.format(response.status_code, response)
            )
        #获取上传链接
        result = response.json()
        if result["code"] != 0:
            raise PdfConversionError(
                '获取上传链接请求失败. 返回数据:{}'.format(result["msg"])
            )
        batch_id = result["data"]["batch_id"]
        #上传链接
        urls = result["data"]["file_urls"]
        #上传文件
        with open(pdf_path_obj, 'rb') as f:
            res_upload = requests.put(urls[0], data=f)
            if res_upload.status_code != 200:
                raise PdfConversionError(f"{urls[0]} 文件上传失败")

            self.logger.info('文件上传成功!')
        #4.获取解析结果
        poll_url = f"{self.config.mineru_base_url}/extract-results/batch/{batch_id}"

        #轮询获取
        start_time = time.time()   #记录当前时间
        timeout_seconds = 600      #设置超时时间
        poll_interval = 3          #轮询间隔
        self.log_step(
            step_name="轮询开始",
            message=f"轮询间隔：{poll_interval}s, 超时时间：{timeout_seconds}s, batch_id: {batch_id}"
        )
        while True:
            elapsed_time = time.time() - start_time
            if elapsed_time > timeout_seconds:
                raise TimeoutError(f"轮询超时,已消耗时间：{int(elapsed_time)}s, batch_id{batch_id}")

             #获取任务结果
            try:
                poll_res = requests.get(poll_url,headers=header,timeout=10)
            except Exception as e:
                self.logger.warning(f"网络请求异常,{poll_interval}s后重试 batch_id{batch_id}")
                self.logger.warning(f"异常信息：{str(e)}")
                time.sleep(poll_interval)
                continue

            if poll_res.status_code != 200:
                raise PdfConversionError(
                    f'[任务轮询]失败，状态码:{poll_res.status_code}'
                )
            poll_res_json = poll_res.json()
            if poll_res_json["code"] != 0:
                raise PdfConversionError(f'[任务轮询]失败，状态码:{poll_res_json["code"]}')

            extract_results = poll_res_json["data"]["extract_result"]
            extract_result = extract_results[0]

            #获取任务的状态值
            data_state = extract_result["state"]
            if data_state == "done":
                self.log_step(
                    step_name="任务轮询",
                    message=f"解析完成s,总耗时：{int(elapsed_time)}s, batch_id: {batch_id}"
                )
                full_zip_url = extract_result["full_zip_url"]
                self.log_step(
                    step_name="任务轮询",
                    message=f"获取全量zip地址成功：{full_zip_url}"
                )
                return full_zip_url

            elif data_state == "failed":
                raise PdfConversionError(
                    f'[任务轮询]失败，错误信息：{extract_result["err_msg"]}'
                )

            else:
                self.log_step(
                    step_name="任务轮询",
                    message=f"处理中.......已耗时：{int(elapsed_time)}s,状态：{data_state},batch_id:{batch_id}"
                )
                time.sleep(poll_interval)
                
    def _step_3_download_and_extract(self,zip_url:str,output_dir_obj:Path,pdf_stem:str) -> str:
        """
       步骤3：下载MinerU解析结果ZIP包并解压，提取目标MD文件
       核心流程：下载ZIP → 清理旧目录并解压 → 查找MD文件 → 重命名统一为PDF同名
       参数：zip_url-ZIP包下载链接；output_dir_obj-输出目录Path；pdf_stem-PDF无后缀纯名称
       返回：最终MD文件的字符串格式绝对路径
       异常：RuntimeError(下载失败)
        """
        #1.下载ZIP包
        self.logger.info(f"【ZIP下载】开始下载ZIP包：{zip_url}....")
        response = requests.get(zip_url)
        #对响应状态进行校验
        if response.status_code != 200:
            raise RuntimeError(f"【ZIP下载】ZIP包下载失败：状态码{response.status_code}，响应结果：{response}")

        #拼接ZIP包保存路径并保存
        zip_save_path = output_dir_obj / f"{pdf_stem}_result.zip"
        with open(zip_save_path, 'wb') as f:
            f.write(response.content)
        self.logger.info(f"【ZIP下载】ZIP包下载成功：保存路径为：{zip_save_path}")

        #2.如果目标文件夹已存在，先删除(确保环境干净)
        extract_target_dir = output_dir_obj / pdf_stem
        if extract_target_dir.exists():
            shutil.rmtree(extract_target_dir)
        self.logger.info(f"【ZIP解压】已清空旧的解压目录：{extract_target_dir}")

        #3.创建解压目录
        extract_target_dir.mkdir(parents=True, exist_ok=True)

        #4.解压
        self.logger.info(f"【ZIP解压】开始解压ZIP包：{output_dir_obj}...")
        with zipfile.ZipFile(zip_save_path, "r") as zip_file_obj:
            zip_file_obj.extractall(extract_target_dir)
        self.logger.info(f"【ZIP解压】ZIP解压完成，解压目录：{extract_target_dir}")

        #5.重命名
        self.logger.info("【MD重命名】找到MinerU生成的full.md文件，并对其进行重命名")
        target_md_file = extract_target_dir / "full.md"
        self.logger.info("【MD重命名】开始将full.md文件进行重命名中")
        new_md_path = target_md_file.with_name(f"{pdf_stem}.md")
        target_md_file.rename(new_md_path)
        self.logger.info(f"【MD重命名】重命名成功，文件名：{pdf_stem}.md")

        return str(new_md_path.absolute())

    def process(self, state: ImportGraphState):
        # self.logger.info(self.config.mineru_api_token)
        # self.logger.info(self.config.mineru_base_url)
        #1.参数校验
        pdf_path_obj, output_dir_obj = self._step_1_validate_paths(state)

        #2.将PDF上传到mineru并轮询结果
        zip_url = self._step_2_upload_and_poll(pdf_path_obj)
        self.log_step(zip_url)


        # 3.下载ZIP包并解压并且得到MD的绝对路径
        md_path = self._step_3_download_and_extract(zip_url,output_dir_obj,pdf_path_obj.stem)


        # 4.将MD文件的内容都取出来
        with open(md_path,"r",encoding="utf-8") as f:
            md_content = f.read()

        #更新state状态
        state["md_path"] = md_path
        state["md_content"] = md_content
        return state
    
    
#PDF转MD单元测试
if __name__ == '__main__':
    setup_logging()
    init_state={
        "pdf_path":r"F:\视频\10-尚硅谷大模型极速版之掌柜智库\2.资料\04-设备手册汇总\doc\hak180产品安全手册.pdf",
        "file_dir":r"F:\\output",
        "task_id":"test-10086"
    }
    node_pdf_to_md = NodePDFToMD()
    result = node_pdf_to_md(init_state)
    json_state = json.dumps(result,ensure_ascii=False, indent=4)