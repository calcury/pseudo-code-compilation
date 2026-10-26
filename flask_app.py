from flask import Flask, request, jsonify, send_file
import subprocess
import tempfile
import os
import re
import time

app = Flask(__name__)


def read_func_py():
    """
    Read the content of func.py in the current directory.
    Returns an empty string if the file does not exist.
    """
    func_path = os.path.join(os.path.dirname(__file__), 'func.py')
    try:
        with open(func_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return ""
    except Exception as e:
        print(f"Error reading func.py: {e}")
        return ""


def pseudo_to_python(pseudo_code):
    """
    Convert pseudocode to Python code.
    """
    # 中文标点转换表
    cn_punct_map = {
        '（': '(',
        '）': ')',
        '：': ':',
        '；': ';',
        '，': ',',
        '。': '.',
        '！': '!',
        '【': '[',
        '】': ']',
        "‘": "'",
        "’": "'",
        '“': '"',
        '”': '"',
        '&&': 'and',
        '||': 'or',
        'mod': '%',
        '–': '-'
    }

    # 统一替换中文标点
    for cn, en in cn_punct_map.items():
        pseudo_code = pseudo_code.replace(cn, en)
    lines = pseudo_code.split('\n')
    python_lines = []
    indent_level = 0
    in_else_block = False

    for i, line in enumerate(lines):
        original_line = line
        line = re.sub(r'\s*:', ':', line)
        line = re.sub(r':\s*', ':', line)
        line = line.rstrip()  # 保留行首空格
        line = re.sub(r'^\s*\d+\s*[:.,：。，·]?\s*', '', line)
        if not line.strip():  # 空行
            continue

        if re.match(r'^(Require|Requires|Returns|Return)\s*:.*$', line, re.IGNORECASE):
            continue

        # True/False 自动替换
        line = re.sub(r'\btrue\b', 'True', line, flags=re.IGNORECASE)
        line = re.sub(r'\bfalse\b', 'False', line, flags=re.IGNORECASE)

        line = re.sub(r'\bif\b', 'if', line, flags=re.IGNORECASE)
        line = re.sub(r'\belse\b', 'else', line, flags=re.IGNORECASE)
        line = re.sub(r'\belseif\b', 'elseif', line, flags=re.IGNORECASE)
        line = re.sub(r'\breturn\b', 'return', line, flags=re.IGNORECASE)
        line = re.sub(r'\bendif\b', 'endif', line, flags=re.IGNORECASE)
        line = re.sub(r'\blet\b', 'let', line, flags=re.IGNORECASE)

        # 处理函数定义
        func_match = re.match(r'^Algorithm:\s*(\w+)\((.*?)\)', line, re.IGNORECASE)
        if func_match:
            func_name = func_match.group(1)
            params = func_match.group(2)
            python_lines.append(f"def {func_name}({params}):")
            indent_level = 1
            continue
        func_match = re.match(r'^Sub-Algorithm:\s*(\w+)\((.*?)\)', line, re.IGNORECASE)
        if func_match:
            func_name = func_match.group(1)
            params = func_match.group(2)
            python_lines.append(f"def {func_name}({params}):")
            indent_level = 1
            continue
        func_match = re.match(r'^SubAlgorithm:\s*(\w+)\((.*?)\)', line, re.IGNORECASE)
        if func_match:
            func_name = func_match.group(1)
            params = func_match.group(2)
            python_lines.append(f"def {func_name}({params}):")
            indent_level = 1
            continue

        # 处理return语句
        if line.startswith('return'):
            python_lines.append(' ' * (4 * indent_level) + line)
            continue

        # 处理条件判断 - if (有then和无then两种情况)
        if_match_with_then = re.match(r'^if\s+(.+)\s+then$', line.strip())
        if_match_without_then = re.match(r'^if\s+(.+)$', line.strip())

        if if_match_with_then:
            condition = if_match_with_then.group(1).strip()
            condition = condition.replace(' mod ', ' % ').replace(' and ', ' and ').replace(' or ', ' or ')
            python_lines.append(' ' * (4 * indent_level) + f"if {condition}:")
            indent_level += 1
            continue
        elif if_match_without_then:
            condition = if_match_without_then.group(1).strip()
            condition = condition.replace(' mod ', ' % ').replace(' and ', ' and ').replace(' or ', ' or ')
            python_lines.append(' ' * (4 * indent_level) + f"if {condition}:")
            indent_level += 1
            continue

        # 处理条件判断 - elseif/else if (有then和无then两种情况)
        elseif_match_with_then = re.match(r'^(elseif|else if)\s+(.+)\s+then$', line.strip())
        elseif_match_without_then = re.match(r'^(elseif|else if)\s+(.+)$', line.strip())

        if elseif_match_with_then:
            condition = elseif_match_with_then.group(2).strip()
            condition = condition.replace(' mod ', ' % ').replace(' and ', ' and ').replace(' or ', ' or ')
            indent_level -= 1  # 回到上一级缩进
            python_lines.append(' ' * (4 * indent_level) + f"elif {condition}:")
            indent_level += 1
            continue
        elif elseif_match_without_then:
            condition = elseif_match_without_then.group(2).strip()
            condition = condition.replace(' mod ', ' % ').replace(' and ', ' and ').replace(' or ', ' or ')
            indent_level -= 1  # 回到上一级缩进
            python_lines.append(' ' * (4 * indent_level) + f"elif {condition}:")
            indent_level += 1
            continue

        # 处理条件判断 - else
        if line.strip() == 'else':
            indent_level -= 1  # 回到上一级缩进
            python_lines.append(' ' * (4 * indent_level) + "else:")
            indent_level += 1
            continue

        # 处理条件判断 - endif
        if line.strip() == 'endif':
            indent_level -= 1  # 结束当前缩进级别
            continue

        # 处理循环结束 - endwhile
        if line.strip() == 'endwhile':
            indent_level -= 1
            continue

        # 处理变量声明
        let_match = re.match(r'^let\s+(\w+)\s*=\s*(.+)$', line.strip())
        if let_match:
            var_name = let_match.group(1)
            var_value = let_match.group(2)
            python_lines.append(' ' * (4 * indent_level) + f"{var_name} = {var_value}")
            continue

        # 处理while循环
        while_match = re.match(r'^while\s+(.+)\s+then$', line.strip())
        if while_match:
            condition = while_match.group(1).strip()
            condition = condition.replace(' mod ', ' % ').replace(' and ', ' and ').replace(' or ', ' or ')
            python_lines.append(' ' * (4 * indent_level) + f"while {condition}:")
            indent_level += 1
            continue

        # 普通执行语句（保持原有缩进）
        if line.strip() and not line.startswith('Algorithm:'):
            # 转换操作符
            converted_line = line.replace(' mod ', ' % ').replace(' and ', ' and ').replace(' or ', ' or ')
            python_lines.append(' ' * (4 * indent_level) + converted_line.strip())

    # 验证缩进是否正确
    final_code = '\n'.join(python_lines)
    return final_code


def extract_function_call(call_input):
    """
    Extract the function call from the input.
    """
    if call_input.startswith('output='):
        return call_input[7:].strip()  # 去掉'output='
    return call_input.strip()


@app.route('/index')
def index():
    """Return the landing page."""
    return send_file('templates/index.html')


@app.route('/edit')
def edit():
    """Return the editor page."""
    return send_file('templates/edit.html')


@app.route('/contact')
def contact():
    """Return the contact page."""
    return send_file('templates/contact.html')


@app.route('/tutorial')
def tutorial():
    """Return the tutorial page."""
    return send_file('document/tutorial.html')


@app.route('/compile', methods=['POST'])
def compile_code():
    """Compile pseudocode to Python (including func.py content)."""
    try:
        data = request.json
        pseudo_code = data.get('pseudo_code', '')

        # 读取func.py内容
        func_code = read_func_py()

        # 转换伪代码为Python
        pseudo_python_code = pseudo_to_python(pseudo_code)

        # 合并代码：func.py在前，伪代码转换的在后
        final_python_code = f"{func_code}\n\n{pseudo_python_code}" if func_code else pseudo_python_code

        return jsonify({
            'success': True,
            'python_code': final_python_code,
            'message': 'Compiled successfully'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'python_code': ''
        })


@app.route('/run', methods=['POST'])
def run_code():
    """Run pseudocode (including func.py content)."""
    try:
        data = request.json
        pseudo_code = data.get('pseudo_code', '')
        function_call = data.get('function_call', '')

        # 读取func.py内容
        func_code = read_func_py()

        # 转换伪代码为Python
        pseudo_python_code = pseudo_to_python(pseudo_code)

        # 提取函数调用
        call_expression = extract_function_call(function_call)

        # 合并代码：func.py在前，伪代码转换的在后
        merged_python_code = f"{func_code}\n\n{pseudo_python_code}" if func_code else pseudo_python_code

        # 创建完整的Python代码
        full_code = f"""# Code from func.py
{func_code}

# Python code converted from pseudocode
{pseudo_python_code}

# Execute the function call
if __name__ == "__main__":
    try:
        import time
        start_time = time.time()
        result = {call_expression}
        end_time = time.time()
        execution_time = end_time - start_time
        print(f"Result: {{result}}")
        print(f"Execution time: {{execution_time:.6f}} s")
    except Exception as e:
        print(f"Error: {{e}}")
        import traceback
        traceback.print_exc()
"""
        # 中文标点转换表
        cn_punct_map = {
            '（': '(',
            '）': ')',
            '：': ':',
            '；': ';',
            '，': ',',
            '。': '.',
            '！': '!',
            '【': '[',
            '】': ']',
            '&&': 'and',
            '||': 'or',
            'mod': '%',
            "‘": "'",
            "’": "'",
            '“': '"',
            '”': '"',
            '–': '-'
        }

        # 统一替换中文标点
        for cn, en in cn_punct_map.items():
            full_code = full_code.replace(cn, en)

        # 创建临时文件运行代码
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(full_code)
            temp_file = f.name

        try:
            # 记录总执行时间（包括启动进程的时间）
            total_start_time = time.time()

            # 运行Python代码
            result = subprocess.run(
                ['python', temp_file],
                capture_output=True,
                text=True,
                timeout=3,  # 3秒超时
                encoding='utf-8'
            )

            total_end_time = time.time()
            total_execution_time = total_end_time - total_start_time

            output = result.stdout
            if result.stderr:
                output += f"\nError:\n{result.stderr}"

        except subprocess.TimeoutExpired:
            total_execution_time = 3.0  # 超时时间
            output = "Error: Timeout (3s)"
        finally:
            # 清理临时文件
            if os.path.exists(temp_file):
                os.unlink(temp_file)

        return jsonify({
            'success': True,
            'output': output,
            'converted_python': full_code,
            'execution_time': total_execution_time,  # 总执行时间（包括进程启动）
            'execution_time_seconds': total_execution_time,
            'execution_time_ms': total_execution_time * 1000  # 毫秒格式
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })
