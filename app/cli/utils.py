"""Evoloop 3.0 CLI 适配器的辅助实用工具函数。

本模块包含超长错误/输出的折叠逻辑（符合 L1/L2 紧凑原则）、用户受挫情绪拦截拦截调解、以及 YAML 格式配置的安全读写与兼容性兜底解析。
"""
from __future__ import annotations

import os
import sys
import re
from typing import Any, Optional

try:
    import yaml
except ImportError:
    yaml = None


def compact_error_text(text: str, max_lines: int = 25) -> str:
    """对超长的 Traceback 堆栈或终端输出进行紧凑折叠，以符合 L1/L2 信息精简原则。

    当文本行数超出 max_lines 时，保留前段与末尾的关键信息，折叠中间的内容并添加折叠标记。

    Args:
        text (str): 待格式化的完整文本。
        max_lines (int): 最大显示行数限制，默认 25 行。

    Returns:
        str: 折叠后的紧凑文本。
    """
    if not text:
        return ""
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
        
    # 如果检测到是 Python 堆栈异常，则优先保留堆栈顶部与底部出错信息
    if "Traceback (most recent call last):" in text:
        header = lines[:3]
        footer = lines[-(max_lines - 4):]
        skipped_count = len(lines) - len(header) - len(footer)
        compacted = (
            header + 
            [f"... [出于可读性折叠了 {skipped_count} 行堆栈帧] ..."] + 
            footer
        )
        return "\n".join(compacted)
        
    half = (max_lines - 1) // 2
    header = lines[:half]
    footer = lines[-half:]
    skipped_count = len(lines) - len(header) - len(footer)
    
    compacted = (
        header + 
        [f"... [出于 L1/L2 精简收纳原则折叠了 {skipped_count} 行输出] ..."] + 
        footer
    )
    return "\n".join(compacted)


def intercept_user_emotion(text: str) -> str:
    """在用户交互时，检测输入中是否包含受挫或恼怒等负面情绪，并拼装调和安抚性质的系统指令。

    Args:
        text (str): 用户的原始输入文本。

    Returns:
        str: 拼接情绪调停引导指令后的最终文本。
    """
    if not text:
        return text
    
    frustration_patterns = [
        r'(?i)wtf', r'(?i)not working', r'(?i)fails again', r'(?i)fuck', 
        r'(?i)糟糕', r'(?i)根本不行', r'(?i)又失败了'
    ]
    
    if any(re.search(p, text) for p in frustration_patterns):
        return text + "\n[System: 用户情绪受挫。请暂停盲目重试，微调沟通姿态，先安抚并提供 step-by-step 的澄清引导，找出卡点所在。]"
    return text


def read_yaml_safe(path: str) -> Optional[dict[str, Any]]:
    """安全读取并解析指定的 YAML 配置文件。

    在环境中未安装 PyYAML 时，尝试通过 JSON 解析器进行降级解析兜底；如解析失败，则安全捕获异常。

    Args:
        path (str): YAML 文件的磁盘绝对或相对路径。

    Returns:
        Optional[dict[str, Any]]: 解析后的字典对象，失败时返回 None。
    """
    if not os.path.exists(path):
        return None
    try:
        content = Path(path).read_text(encoding="utf-8")
        if yaml is not None:
            return yaml.safe_load(content)
        else:
            # 降级处理：如果没有 PyYAML 库，对于简单的键值对直接尝试用 JSON 反序列化
            import json
            try:
                return json.loads(content)
            except Exception:
                raise ImportError("pyyaml is required to read complex YAML files.")
    except Exception as e:
        print(f"Error reading YAML file at {path}: {compact_error_text(str(e))}", file=sys.stderr)
        return None


def write_yaml_safe(path: str, data: dict[str, Any]) -> bool:
    """将数据字典以 YAML 格式安全地写入目标文件中。

    如缺少 PyYAML，则以降级 JSON 格式进行持久化写入。

    Args:
        path (str): 写入文件的目标路径。
        data (dict[str, Any]): 需要写入的数据字典结构。

    Returns:
        bool: 是否写入成功。
    """
    try:
        from pathlib import Path
        dest = Path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        
        if yaml is not None:
            content = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
        else:
            import json
            content = json.dumps(data, ensure_ascii=False, indent=2)
            
        dest.write_text(content, encoding="utf-8")
        return True
    except Exception as e:
        print(f"Error writing YAML file to {path}: {compact_error_text(str(e))}", file=sys.stderr)
        return False


# 供内部使用的 Path 包装器
from pathlib import Path
