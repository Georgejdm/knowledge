# processor/import_processor/nodes/node_entry.py
import json
import logging
from pathlib import Path

from processor.import_processor.base import BaseNode, setup_logging
from processor.import_processor.exceptions import StateFieldError, FileProcessingError, ValidationError
from processor.import_processor.state import ImportGraphState


class NodeEntry(BaseNode):
    """
    入口节点：任务分发
    """

    name = "node_entry"

    def process(self, state: ImportGraphState):
        #1.获取上传的文件
        import_file_path = state.get('import_file_path')

        #判断路径是否为空
        if not import_file_path:
            raise StateFieldError(
                node_name=self.name,
                field_name='import_file_path',
                expected_type=str
            )

        #2.转换Path标准化对象
        import_file_path_obj = Path(import_file_path)
        #判断文件是否存在
        if not import_file_path_obj.exists():
            raise FileProcessingError(
                message=f"文件{import_file_path_obj.name}不存在"
            )

        #3.检查文件后缀
        if import_file_path_obj.suffix == '.pdf':
            state["is_pdf_read_enabled"] = True
            state["pdf_path"] = import_file_path
        elif import_file_path_obj.suffix == '.md':
            state["is_md_read_enabled"] = True
            state["md_path"] = import_file_path
        else:
            raise ValidationError(
                message=f"文件的后缀格式{import_file_path_obj.suffix}不支持"
            )

        #4.获取上传文件的标题，更新到state中
        state["file_title"] = import_file_path_obj.stem

        #5.返回到state
        return state


#单元测试
if __name__ == '__main__':
    setup_logging()
    # init_state = {
    #     "import_file_path":r"F:\视频\10-尚硅谷大模型极速版之掌柜智库\2.资料\04-设备手册汇总\doc\hak180产品安全手册.pdf"
    # }
    init_state = {
        "import_file_path":r"F:\视频\10-尚硅谷大模型极速版之掌柜智库\2.资料\04-设备手册汇总\doc\123.txt"
    }
    node_entry = NodeEntry()
    result = node_entry(init_state)

    logging.getLogger().info(json.dumps(result ,ensure_ascii=False, indent=4))