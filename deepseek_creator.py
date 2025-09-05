import os
import requests
import json
import time
import readline
import re
import tempfile
import subprocess
from typing import List, Dict, Any
from datetime import datetime

# Цвета для вывода
COLOR_THINKING = "\033[90m"  # Темно-серый (размышления)
COLOR_RESPONSE = "\033[0m"   # Стандартный (ответ)
COLOR_PROMPT = "\033[94m"    # Синий (приглашение ввода)
COLOR_RESET = "\033[0m"      # Сброс цвета
COLOR_FILE = "\033[93m"      # Желтый (информация о файлах)
COLOR_ERROR = "\033[91m"     # Красный (ошибки)
COLOR_INFO = "\033[96m"      # Голубой (информация)
COLOR_EDITOR = "\033[92m"    # Зеленый (редактор)

class OpenRouterFileCreator:
    def __init__(self, api_keys: List[str]):
        self.api_keys = api_keys
        self.current_key_index = 0
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.headers = {
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "AI Assistant"
        }
        self.working_directory = os.getcwd()  # Текущая рабочая директория
        self.history_file = os.path.expanduser("~/.assistant_chat_history.json")
        self.chat_history = self.load_chat_history()  # Загружаем историю чата

    def load_chat_history(self) -> List[Dict]:
        """Загрузить историю чата из файла"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"{COLOR_ERROR}Ошибка при загрузке истории: {str(e)}{COLOR_RESET}")
        return []

    def save_chat_history(self):
        """Сохранить историю чата в файл"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.chat_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"{COLOR_ERROR}Ошибка при сохранении истории: {str(e)}{COLOR_RESET}")

    def get_next_key(self) -> str:
        """Получить следующий API ключ с ротацией"""
        key = self.api_keys[self.current_key_index]
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        return key

    def read_file(self, filepath: str) -> str:
        """Чтение содержимого файла"""
        try:
            # Если путь относительный, добавляем текущую рабочую директорию
            if not filepath.startswith('/'):
                filepath = os.path.join(self.working_directory, filepath)
            
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            return content
        except Exception as e:
            return f"Ошибка при чтении файла: {str(e)}"

    def list_files(self, directory: str = None) -> str:
        """Список файлов в директории"""
        try:
            if not directory:
                directory = self.working_directory
            elif not directory.startswith('/'):
                directory = os.path.join(self.working_directory, directory)
            
            # Проверяем существование директории
            if not os.path.exists(directory):
                return f"Директория не существует: {directory}"
            
            files = os.listdir(directory)
            return "\n".join(files)
        except Exception as e:
            return f"Ошибка при получении списка файлов: {str(e)}"

    def get_system_info(self) -> str:
        """Получить информацию о системе для системного промпта"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        files_in_dir = self.list_files()
        
        return f"""Текущее время: {current_time}
Рабочая директория: {self.working_directory}
Файлы в текущей директории:
{files_in_dir}"""

    def execute_action(self, action_data: Dict) -> str:
        """Выполнить действия из JSON"""
        try:
            action = action_data.get("action")
            
            if action == "create_file":
                filename = action_data["filename"]
                permissions = action_data["permissions"]
                content = action_data["content"]

                # Создаем директорию, если нужно
                os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else ".", exist_ok=True)

                # Создаем файл
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(content)

                # Устанавливаем права
                os.chmod(filename, int(permissions, 8))
                
                return f"Файл '{filename}' создан с правами {permissions}"
            
            elif action == "read_file":
                filename = action_data["filename"]
                content = self.read_file(filename)
                return f"Содержимое файла '{filename}':\n{COLOR_FILE}{content}{COLOR_RESPONSE}"
            
            elif action == "list_files":
                directory = action_data.get("directory")
                files = self.list_files(directory)
                return f"Файлы в директории '{directory if directory else self.working_directory}':\n{COLOR_FILE}{files}{COLOR_RESPONSE}"
            
            elif action == "change_directory":
                new_dir = action_data.get("directory", "")
                if new_dir:
                    try:
                        os.chdir(new_dir)
                        self.working_directory = os.getcwd()
                        return f"Рабочая директория изменена на: {self.working_directory}"
                    except Exception as e:
                        return f"Ошибка при изменении директории: {str(e)}"
                else:
                    return "Не указана директория для изменения"
            
            else:
                return f"Неизвестное действие: {action}"
        except KeyError as e:
            return f"Отсутствует обязательное поле в JSON: {str(e)}"
        except Exception as e:
            return f"Ошибка при выполнении действия: {str(e)}"

    def extract_json_objects(self, text: str) -> List[Dict]:
        """Извлечь все JSON-объекты из текста"""
        json_objects = []
        
        # Улучшенный поиск JSON-объектов
        json_patterns = [
            r'\{[^{}]*\}',  # Простые JSON-объекты
            r'\{.*?\}(?=\s*(?:\{|$))',  # Более сложные объекты
        ]
        
        for pattern in json_patterns:
            matches = re.finditer(pattern, text, re.DOTALL)
            for match in matches:
                try:
                    json_str = match.group()
                    # Очищаем строку от лишних символов
                    json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_str)
                    json_obj = json.loads(json_str)
                    json_objects.append(json_obj)
                except json.JSONDecodeError:
                    continue
        
        return json_objects

    def clean_input(self, text: str) -> str:
        """Очистка ввода от лишних символов"""
        # Удаляем лишние пробелы в начале и конце
        text = text.strip()
        # Заменяем множественные пробелы на один, но сохраняем переносы строк
        text = re.sub(r'[ \t]+', ' ', text)
        return text

    def open_editor(self, initial_content: str = "") -> str:
        """Открыть текстовый редактор для ввода многострочного текста"""
        # Создаем временный файл
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.txt', delete=False, encoding='utf-8') as tmpfile:
            tmp_path = tmpfile.name
            if initial_content:
                tmpfile.write(initial_content)
        
        try:
            # Пытаемся использовать nano (стандартный редактор в Ubuntu)
            editor = os.environ.get('EDITOR', 'nano')
            subprocess.call([editor, tmp_path])
            
            # Читаем содержимое файла после редактирования
            with open(tmp_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return content
        except Exception as e:
            print(f"{COLOR_ERROR}Ошибка при открытии редактора: {str(e)}{COLOR_RESET}")
            print(f"{COLOR_INFO}Используется встроенный многострочный редактор...{COLOR_RESET}")
            
            # Если не удалось открыть внешний редактор, используем встроенный
            return self.builtin_editor(initial_content)
        finally:
            # Удаляем временный файл
            try:
                os.unlink(tmp_path)
            except:
                pass

    def builtin_editor(self, initial_content: str = "") -> str:
        """Встроенный многострочный редактор"""
        print(f"{COLOR_EDITOR}Встроенный редактор. Введите текст. Для завершения введите '.' на отдельной строке{COLOR_RESET}")
        print(f"{COLOR_EDITOR}==================================================={COLOR_RESET}")
        
        lines = []
        if initial_content:
            lines = initial_content.split('\n')
            for line in lines:
                print(f"{COLOR_EDITOR}{line}{COLOR_RESET}")
        
        while True:
            try:
                line = input()
                if line == '.':
                    break
                lines.append(line)
            except EOFError:
                break
        
        return '\n'.join(lines)

    def send_message(self, prompt: str) -> str:
        """Отправить сообщение через OpenRouter API"""
        # Очищаем ввод от лишних символов
        cleaned_prompt = self.clean_input(prompt)
        
        # Добавляем текущий промпт в историю
        self.chat_history.append({"role": "user", "content": cleaned_prompt, "timestamp": datetime.now().isoformat()})
        self.save_chat_history()  # Сохраняем историю после добавления сообщения
        
        # Формируем системное сообщение с информацией о системе и историей
        system_info = self.get_system_info()
        
        system_message = f"""Ты - универсальный ассистент. Ты можешь создавать файлы, читать файлы, отвечать на вопросы и помогать с различными задачами.

Информация о системе:
{system_info}

ВАЖНЫЕ ИНСТРУКЦИИ:
1. Внимательно анализируй запрос пользователя перед выполнением действий
2. Выполняй только те действия, которые явно запрошены пользователем
3. Если запрос не требует создания файлов, не создавай их
4. Всегда проверяй существование файлов и директорий перед операциями с ними

Для создания файлов используй формат JSON:
{{
    "action": "create_file",
    "filename": "example.txt",
    "permissions": "644",
    "content": "Содержимое файла"
}}

Для чтения файлов используй формат JSON:
{{
    "action": "read_file",
    "filename": "example.txt"
}}

Для получения списка файлов в директории используй формат JSON:
{{
    "action": "list_files",
    "directory": "/optional/path"
}}

Для изменения рабочей директории используй формат JSON:
{{
    "action": "change_directory",
    "directory": "/new/path"
}}

Всегда сначала показывай свои размышления, разделяя их символом |, а затем давай ответ.

Если тебе нужно выполнить несколько действий, перечисли их все в одном сообщении, используя несколько JSON-объектов."""

        # Формируем полный список сообщений (системное + история + текущее)
        messages = [{"role": "system", "content": system_message}]
        
        # Добавляем только последние 10 сообщений из истории, чтобы не превысить лимит токенов
        recent_history = self.chat_history[-10:] if len(self.chat_history) > 10 else self.chat_history
        for msg in recent_history:
            # Пропускаем системные сообщения и временные метки
            if msg["role"] in ["user", "assistant"]:
                messages.append({"role": msg["role"], "content": msg["content"]})

        payload = {
            "model": "deepseek/deepseek-chat",
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 2000
        }

        # Пробуем все ключи по очереди при ошибках
        for attempt in range(len(self.api_keys)):
            current_key = self.get_next_key()
            self.headers["Authorization"] = f"Bearer {current_key}"

            try:
                response = requests.post(self.api_url, headers=self.headers, json=payload)
                
                # Проверяем статус ответа
                if response.status_code == 429:
                    print(f"{COLOR_THINKING}Ключ превысил лимит, пробую следующий...{COLOR_RESET}")
                    continue
                
                response.raise_for_status()
                
                # Извлекаем содержимое ответа
                return response.json()["choices"][0]["message"]["content"]
                
            except requests.exceptions.RequestException as e:
                print(f"{COLOR_THINKING}Ошибка с ключом: {str(e)}{COLOR_RESET}")
                if hasattr(e, 'response') and e.response is not None and hasattr(e.response, 'text'):
                    print(f"{COLOR_THINKING}Детали ошибки: {e.response.text}{COLOR_RESET}")
                if attempt == len(self.api_keys) - 1:
                    raise Exception("Все API ключи исчерпали лимит или произошла ошибка")
                time.sleep(1)

        raise Exception("Не удалось выполнить запрос после всех попыток")

    def process_response(self, response: str) -> str:
        """Обработать ответ от API"""
        # НЕ очищаем ответ от переносов строк - это важно для форматирования
        
        # Разделяем размышления и ответ
        thinking = ""
        answer = response
        
        if "|" in response:
            parts = response.split("|", 1)
            if len(parts) > 1:
                thinking = parts[0].strip()
                answer = parts[1]
                
                # Выводим размышления
                if thinking:
                    print(f"{COLOR_THINKING}{thinking}{COLOR_RESET}")
        
        # Извлекаем все JSON-объекты из ответа
        json_objects = self.extract_json_objects(answer)
        results = []
        
        # Выполняем все действия из JSON-объектов
        for json_obj in json_objects:
            try:
                result = self.execute_action(json_obj)
                results.append(result)
            except Exception as e:
                results.append(f"{COLOR_ERROR}Ошибка при выполнении действия: {str(e)}{COLOR_RESPONSE}")
        
        # Если нашли JSON-действия, возвращаем результаты
        if results:
            final_result = "\n".join(results)
            # Добавляем ответ ассистента в историю
            self.chat_history.append({"role": "assistant", "content": final_result, "timestamp": datetime.now().isoformat()})
            self.save_chat_history()  # Сохраняем историю после ответа
            return final_result
        
        # Если это обычный ответ, просто возвращаем его
        self.chat_history.append({"role": "assistant", "content": answer, "timestamp": datetime.now().isoformat()})
        self.save_chat_history()  # Сохраняем историю после ответа
        return answer

def input_with_history(prompt):
    """Функция для ввода с поддержкой истории и редактирования"""
    try:
        # Включаем поддержку истории readline
        line = input(f"{COLOR_PROMPT}{prompt}{COLOR_RESET}")
        return line
    except (EOFError, KeyboardInterrupt):
        return "quit"

def main():
    # API ключи OpenRouter
    api_keys = [
        "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",
        "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"
    ]

    # Настройка readline для поддержки истории
    try:
        import readline
        readline.parse_and_bind("tab: complete")
        input_history_file = os.path.expanduser("~/.assistant_input_history")
        if os.path.exists(input_history_file):
            readline.read_history_file(input_history_file)
    except ImportError:
        pass

    creator = OpenRouterFileCreator(api_keys)

    print(f"{COLOR_RESPONSE}{'=' * 60}")
    print("Универсальный AI Ассистент")
    print("Может создавать файлы, читать файлы, отвечать на вопросы и помогать с задачами")
    print("Команды: :edit - открыть редактор, :quit - выйти")
    print(f"Текущая директория: {creator.working_directory}")
    print(f"Загружено сообщений из истории: {len(creator.chat_history)}")
    print("Введите сообщение (или 'quit' для выхода):")
    print("=" * 60 + COLOR_RESET)
    
    try:
        while True:
            prompt = input_with_history("\n> ").strip()
            
            # Обработка специальных команд
            if prompt.lower() in ['quit', 'exit', 'q']:
                break
            elif prompt.lower() in [':edit', 'edit']:
                # Открываем редактор для многострочного ввода
                editor_content = creator.open_editor()
                if editor_content.strip():
                    print(f"{COLOR_THINKING}Обрабатываю запрос из редактора...{COLOR_RESET}")
                    response = creator.send_message(editor_content)
                    result = creator.process_response(response)
                    print(f"{COLOR_RESPONSE}{result}{COLOR_RESPONSE}")
                continue
            elif prompt.lower() in [':clear', 'clear']:
                # Очищаем историю
                creator.chat_history = []
                creator.save_chat_history()
                print(f"{COLOR_INFO}История чата очищена{COLOR_RESET}")
                continue
                
            if not prompt:
                continue

            print(f"{COLOR_THINKING}Обрабатываю запрос...{COLOR_RESET}")
            response = creator.send_message(prompt)
            result = creator.process_response(response)
            print(f"{COLOR_RESPONSE}{result}{COLOR_RESPONSE}")
            
    except KeyboardInterrupt:
        print(f"\n{COLOR_RESPONSE}Программа завершена.{COLOR_RESET}")
    except Exception as e:
        print(f"{COLOR_RESPONSE}Ошибка: {str(e)}{COLOR_RESET}")
    finally:
        # Сохраняем истории
        try:
            readline.write_history_file(input_history_file)
        except:
            pass
        
        creator.save_chat_history()
        print(f"{COLOR_INFO}История чата сохранена в {creator.history_file}{COLOR_RESET}")

if __name__ == "__main__":
    # Проверяем наличие необходимых библиотек
    try:
        import requests
    except ImportError:
        print("Установите библиотеку requests: pip install requests")
        exit(1)
    
    main()