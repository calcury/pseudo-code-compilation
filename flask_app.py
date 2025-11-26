from flask import Flask, request, jsonify, send_file
import subprocess
import tempfile
import os
import re

app = Flask(__name__)

# 读取func.py文件的内容
def read_func_py():
    """
    读取当前目录下的func.py文件内容
    如果文件不存在则返回空字符串
    """
    func_path = os.path.join(os.path.dirname(__file__), 'func.py')
    try:
        with open(func_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return ""
    except Exception as e:
        print(f"读取func.py时出错: {e}")
        return ""

def pseudo_to_python(pseudo_code):
    """
    将伪代码转换为Python代码
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
        '】': ']'
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
        line = line.rstrip()  # 保留行首空格

        if not line.strip():  # 空行
            python_lines.append('')
            continue

        # 去除行尾注释
        line = line.split('//')[0].strip()
        if not line:
            continue

        if re.match(r'^(Require|Requires|Returns|Return)\s*:.*$', line, re.IGNORECASE):
            continue

        # True/False 自动替换
        line = re.sub(r'\btrue\b', 'True', line, flags=re.IGNORECASE)
        line = re.sub(r'\bfalse\b', 'False', line, flags=re.IGNORECASE)

        # 处理函数定义
        func_match = re.match(r'^Algorithm:\s*(\w+)\((.*?)\)', line)
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

        # 处理条件判断 - if
        if_match = re.match(r'^if\s+(.+)\s+then$', line.strip())
        if if_match:
            condition = if_match.group(1).strip()
            condition = condition.replace(' mod ', ' % ').replace(' and ', ' and ').replace(' or ', ' or ')
            python_lines.append(' ' * (4 * indent_level) + f"if {condition}:")
            indent_level += 1
            continue

        # 处理条件判断 - elseif/else if
        elseif_match = re.match(r'^(elseif|else if)\s+(.+)\s+then$', line.strip())
        if elseif_match:
            condition = elseif_match.group(2).strip()
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
    从输入中提取函数调用
    """
    if call_input.startswith('output='):
        return call_input[7:].strip()  # 去掉'output='
    return call_input.strip()

@app.route('/')
def index():
    """返回前端页面"""
    return send_file('templates/index.html')

@app.route('/compile', methods=['POST'])
def compile_code():
    """编译伪代码为Python（包含func.py的内容）"""
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
            'message': '编译成功'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'python_code': ''
        })

@app.route('/run', methods=['POST'])
def run_code():
    """运行伪代码（包含func.py的内容）"""
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
        full_code = f"""# 来自func.py的代码
{func_code}

# 伪代码转换的Python代码
{pseudo_python_code}

# 执行函数调用
if __name__ == "__main__":
    try:
        result = {call_expression}
        print(f"输出结果: {{result}}")
    except Exception as e:
        print(f"错误: {{e}}")
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
            '】': ']'
        }

        # 统一替换中文标点
        for cn, en in cn_punct_map.items():
            full_code = full_code.replace(cn, en)

        # 创建临时文件运行代码
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(full_code)
            temp_file = f.name

        try:
            # 运行Python代码
            result = subprocess.run(
                ['python', temp_file],
                capture_output=True,
                text=True,
                timeout=10,  # 10秒超时
                encoding='utf-8'
            )

            output = result.stdout
            if result.stderr:
                output += f"\n错误信息:\n{result.stderr}"

        except subprocess.TimeoutExpired:
            output = "错误: 代码执行超时（10秒）"
        finally:
            # 清理临时文件
            if os.path.exists(temp_file):
                os.unlink(temp_file)

        return jsonify({
            'success': True,
            'output': output,
            'converted_python': full_code
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })
