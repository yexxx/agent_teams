#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hello.py - 简单的Hello World程序

这是一个简单的Python脚本，演示spec流程。
主要功能是打印"Hello, World!"到标准输出。
"""

# 常量定义
HELLO_MESSAGE = "Hello, World!"


def print_hello() -> None:
    """
    打印Hello World消息到标准输出
    
    功能：
    - 打印固定消息"Hello, World!"
    - 输出后自动添加换行符
    
    参数：
        无
    
    返回值：
        无
    
    示例：
        >>> print_hello()
        Hello, World!
    """
    print(HELLO_MESSAGE)


def main() -> int:
    """
    主执行函数
    
    功能：
    - 协调整个脚本的执行流程
    - 调用打印函数
    - 返回退出码
    
    参数：
        无
    
    返回值：
        int: 退出码，0表示成功执行
    
    示例：
        >>> exit_code = main()
        Hello, World!
        >>> exit_code
        0
    """
    print_hello()
    return 0


if __name__ == "__main__":
    # 确保脚本可以直接执行，也可以作为模块导入
    exit_code = main()
    exit(exit_code)