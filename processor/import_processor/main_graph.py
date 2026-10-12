import json
import logging

from langgraph.graph import StateGraph
from langgraph.constants import END

from processor.import_processor.base import setup_logging
from processor.import_processor.nodes.node_bge_embedding import NodeBGEEmbedding
from processor.import_processor.nodes.node_document_split import NodeDocumentSplit
from processor.import_processor.nodes.node_entry import NodeEntry
from processor.import_processor.nodes.node_import_milvus import NodeImportMilvus
from processor.import_processor.nodes.node_item_name_recognition import NodeItemNameRecognition
from processor.import_processor.nodes.node_md_img import NodeMDImg
from processor.import_processor.nodes.node_pdf_to_md import NodePDFToMD
from processor.import_processor.state import ImportGraphState


class KBImportWorkflow:
    """知识库导入流"""
    def __init__(self):
        """
        初始化工作流
        """
        self._compiled_graph = None

    @property
    def graph(self):
        """懒加载：只在第一次使用时编译图"""
        if self._compiled_graph is None:
            self._compiled_graph = self.build_graph()
        return self._compiled_graph

    @staticmethod
    def route_after_entry(state: ImportGraphState) -> str:

        if state.get("is_pdf_read_enabled"):
            return "node_pdf_to_md"
        elif state.get("is_md_read_enabled"):
            return "node_md_img"
        else:
            return END

    def build_graph(self):
        #1.初始化图
        graph = StateGraph(ImportGraphState)

        # 2. 注册节点到工作流
        graph.add_node("node_entry", NodeEntry())
        graph.add_node("node_pdf_to_md", NodePDFToMD())
        graph.add_node("node_md_img", NodeMDImg())
        graph.add_node("node_document_split", NodeDocumentSplit())
        graph.add_node("node_item_name_recognition", NodeItemNameRecognition())
        graph.add_node("node_bge_embedding", NodeBGEEmbedding())
        graph.add_node("node_import_milvus", NodeImportMilvus())

        #3.设置入口节点
        graph.set_entry_point("node_entry")

        #4.注册条件边
        graph.add_conditional_edges(
            "node_entry",
            self.route_after_entry,
            {
                "node_md_img": "node_md_img",
                "node_pdf_to_md": "node_pdf_to_md",
                END: END
            }
        )

        # 5. 注册顺序边
        graph.add_edge("node_pdf_to_md", "node_md_img")
        graph.add_edge("node_md_img", "node_document_split")
        graph.add_edge("node_document_split", "node_item_name_recognition")
        graph.add_edge("node_item_name_recognition", "node_bge_embedding")
        graph.add_edge("node_bge_embedding", "node_import_milvus")
        graph.add_edge("node_import_milvus", END)

        #6.编译工作流
        return graph.compile()

    def run(self, state: ImportGraphState,stream:bool = False):
        """
                统一执行入口，支持切换invoke/stream
                :param state: 初始状态
                :param stream: 是否流式输出
                :return: 执行结果
        """
        #打印图结构
        self.graph.get_graph().print_ascii()

        if stream:
            # return self.graph.stream(state,stream_mode="values")
            return self.graph.stream(state)
        else:
            return self.graph.invoke(state)


if __name__ == '__main__':
    # #定义初始化状态
    # init_state = {"import_file_path": r"D:\doc\hak180产品安全手册.pdf"}
    # workflow = KBImportWorkflow()
    #
    # # 方式1：实例化后使用（推荐方式，可复用）
    # workflow = KBImportWorkflow()
    # for event in workflow.run(init_state, stream=True):
    #     print(f"state: {event}")
    #
    # # 方式2：非流式执行
    # final_state = workflow.run(init_state, stream=False)
    # print(json.dumps(final_state, ensure_ascii=False, indent=4))

    setup_logging()
    
    init_state = {
        "import_file_path": r"F:\视频\10-尚硅谷大模型极速版之掌柜智库\2.资料\04-设备手册汇总\doc\hak180使用说明书.pdf",
        "file_dir": r"F:\output"
    }
    workflow = KBImportWorkflow()
    final_state = workflow.run(init_state)
    logging.getLogger().info(workflow.graph.get_graph().print_ascii())
