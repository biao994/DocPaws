"""统计/列表题识别：避免照搬过期历史。"""
from docpaws.usecases.chat_agent_tools import is_scope_inventory_question


def test_inventory_question_positive():
    assert is_scope_inventory_question("这个知识库有多少个文件")
    assert is_scope_inventory_question("有几个文档")
    assert is_scope_inventory_question("有哪些文件")
    assert is_scope_inventory_question("列一下文档")


def test_inventory_question_negative():
    assert not is_scope_inventory_question("2023_PDF2讲了啥")
    assert not is_scope_inventory_question("总结一下合同要点")
    assert not is_scope_inventory_question("")
