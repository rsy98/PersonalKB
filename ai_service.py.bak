# 删除原有的 DeepSeek API 调用，替换为 Ollama 本地调用

import requests
import json
import re

class AIService:
    def __init__(self):
        self.enabled = True
        self.base_url = "http://localhost:11434"  # Ollama 默认地址
        self.model = "deepseek-r1:8b"
        # self.model = "deepseek-r1:32b"
        # self.model = "deepseek-r1:14b"

    def _call_ollama(self, prompt, system_prompt=None):
        try:
            import requests

            # 构建消息，明确要求直接回答
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            # 在用户消息中明确要求直接回答
            direct_prompt = prompt + "\n\n请直接给出答案，不需要思考过程。"
            messages.append({"role": "user", "content": direct_prompt})

            payload = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": 0.3,  # 降低随机性，让回答更直接
                    "top_p": 0.9,
                    "top_k": 40
                }
            }

            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=120
            )
            response.raise_for_status()

            result = response.json()
            return result['message']['content']

        except Exception as e:
            print(f"Ollama API 调用失败: {str(e)}")
            return None

    def analyze_knowledge_item(self, title, content, tags, category):
        """分析知识条目"""
        prompt = f"""请分析以下知识条目：

标题：{title}
分类：{category}
标签：{', '.join(tags) if tags else '无'}
内容：{content[:2000]}...

请提供：
1. 内容摘要
2. 关键知识点
3. 相关主题建议
4. 学习建议"""

        system_prompt = "你是一个专业的知识管理助手，擅长分析和总结知识内容。"

        analysis = self._call_ollama(prompt, system_prompt)

        return {
            "analysis": analysis,
            "summary": f"AI分析完成: {title}",
            "related_topics": ["相关主题1", "相关主题2"]  # 可以进一步解析AI返回的内容
        }

    def generate_questions(self, content):
        """生成测试问题"""
        prompt = f"""基于以下内容生成3-5个测试问题：

内容：{content[:1500]}...

请生成多种类型的问题（概念理解、应用实践、分析评价等）："""

        system_prompt = "你是一个教育专家，擅长设计有启发性的测试问题。"

        questions_text = self._call_ollama(prompt, system_prompt)

        # 简单解析返回的问题文本
        questions = []
        if questions_text:
            lines = questions_text.split('\n')
            for line in lines:
                line = line.strip()
                if line and (line.startswith('1.') or line.startswith('2.') or
                           line.startswith('3.') or line.startswith('4.') or
                           line.startswith('5.') or line.startswith('-') or
                           line.startswith('•')):
                    # 移除编号和标记
                    question = line.lstrip('12345.-• ').strip()
                    if question:
                        questions.append(question)

        return questions if questions else ["请基于内容自行设计问题"]

    def improve_writing(self, content):
        """改进写作"""
        prompt = f"""请改进以下内容的写作，使其更清晰、专业：

{content}

请直接返回改进后的文本："""

        system_prompt = "你是一个专业的编辑，擅长改进文本的清晰度和专业性。"

        improved = self._call_ollama(prompt, system_prompt)
        return improved if improved else content

    def chat_with_knowledge(self, question, context_items, chat_history=None):
        # 构建上下文，包含聊天历史
        context = "对话历史:\n"
        if chat_history:
            for msg in chat_history[-6:]:  # 只保留最近6条消息作为上下文
                if msg.get('role') == 'user':
                    context += f"用户: {msg.get('content', '')}\n"
                elif msg.get('role') == 'assistant':
                    context += f"助手: {msg.get('content', '')}\n"

        context += "\n当前知识上下文:\n"
        context += "\n".join([f"标题: {item.get('title', '')}\n内容: {item.get('content', '')[:300]}"
                             for item in context_items[:2]])

        prompt = f"{context}\n\n请基于以上信息回答用户问题：{question}"
        # prompt = f"基于以下知识回答问题：\n\n{context}\n\n问题：{question}"

        full_response = self._call_ollama(prompt, "你是一个知识库助手")

        # 解析响应，分离思考过程和答案
        thinking, answer = self._parse_thinking_and_answer(full_response)

        return {
            "thinking": thinking,
            "answer": answer,
            "full_response": full_response  # 保留完整响应用于调试
        }

    def _parse_thinking_and_answer(self, response):
        """解析响应，分离思考过程和最终答案"""
        if not response:
            return "", "抱歉，暂时无法回答这个问题。"

        # DeepSeek 模型通常使用「」或类似的标记来表示思考过程
        # 我们可以根据这个特点来分离内容

        # 方法1：查找「」标记
        import re
        thinking_parts = re.findall(r'「(.*?)」', response, re.DOTALL)
        thinking = " ".join(thinking_parts).strip()

        # 从原始响应中移除思考部分得到答案
        answer = re.sub(r'「.*?」', '', response).strip()

        # 如果上述方法没有找到思考过程，尝试其他方法
        if not thinking or not answer:
            # 方法2：查找明显的分隔符
            if "答案：" in response or "回答：" in response:
                parts = re.split(r'(?:答案|回答)[：:]', response, maxsplit=1)
                if len(parts) > 1:
                    thinking = parts[0].strip()
                    answer = parts[1].strip()
                else:
                    thinking = ""
                    answer = response
            else:
                # 方法3：简单分割（取前1/3作为思考，后2/3作为答案）
                lines = response.split('\n')
                if len(lines) > 3:
                    thinking = '\n'.join(lines[:len(lines)//3])
                    answer = '\n'.join(lines[len(lines)//3:])
                else:
                    thinking = ""
                    answer = response

        # 清理格式
        thinking = self._clean_text(thinking)
        answer = self._clean_text(answer)

        return thinking, answer

    def _clean_text(self, text):
        """清理文本格式"""
        if not text:
            return text

        # 移除多余的空行
        text = re.sub(r'\n\s*\n', '\n\n', text)
        # 移除首尾空白
        text = text.strip()

        return text



ai_service = AIService()
