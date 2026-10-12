from typing import Dict

from processor.import_processor.base import BaseNode, setup_logging
import logging

class TestNode(BaseNode):
    name = 'TestNode'
    def process(self,state:Dict) -> Dict:

        self.logger.info(f'{self.name}正在执行')
        self.logger.debug(f'{self.name}正在debug')
        self.logger.warning(f'{self.name}warning')


        return {}
if __name__ == '__main__':

    setup_logging(logging.DEBUG)

    test_node = TestNode()
    test_node({"abc":123})