"""用于大语言模型上下文 Token 计数的工具服务。

本模块提供统一的 TokenCounter 计数器，优先利用 `tiktoken` 提供与 OpenAI 规范相符的高精度分词计数；
当库不可用或运行出错时，降级为基于字符长度估算的安全启发式计数算法。
"""
from __future__ import annotations


class TokenCounter:
    """高精度与启发式双通路 Token 计数器类。

    维护分词器实例，在不同模型背景下自适应计算文本 Token 长度。
    """

    def __init__(self, model: str = "gpt-4"):
        """初始化 TokenCounter 实例。

        Args:
            model: 目标大语言模型名称，默认 "gpt-4"，用于匹配 tiktoken 编码格式。
        """
        self.model = model
        try:
            import tiktoken
            self.encoding = tiktoken.encoding_for_model(model)
        except Exception:
            # 库未安装或模型映射不存在时的静默降级处理
            self.encoding = None

    def count(self, text: str) -> int:
        """计算指定文本的 Token 消耗数量。

        优先通过 tiktoken 编码计算；如果库缺失或编码失败，
        则降级采用启发式估算方法：中英文混合场景下，通常取长度的 1/2 作为保守预估。

        Args:
            text: 待计数的文本。

        Returns:
            int: 预估或精确计算出的 Token 数量。
        """
        if not text:
            return 0
        
        # 优先使用 tiktoken 编码分词计数
        if self.encoding:
            try:
                return len(self.encoding.encode(text))
            except Exception:
                pass
        
        # 启发式降级估算：1 个 Token 大约等于 1.5 个汉字或 4 个英文单词
        # 在混合语言或带有大量符号的代码场景中，使用 字符总长度 // 2 可以实现一个稳定且略微偏高的保守估算
        return max(1, len(text) // 2)

