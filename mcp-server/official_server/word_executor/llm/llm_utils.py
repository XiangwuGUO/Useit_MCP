import os
import re
import ast
import base64
from PIL import Image

def gbk_encode_decode(text):
    # Encode the text to GBK, ignoring characters that can't be encoded
    # Then decode it back to a string
    cleaned_text = text.encode('gbk', 'ignore').decode('gbk')
    return cleaned_text

def is_image_path(text):
    # Checking if the input text ends with typical image file extensions
    image_extensions = (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif")
    if text.endswith(image_extensions):
        return True
    else:
        return False

def resize_image(image_path: str, new_width: int, new_height: int) -> str:
    """Resize image to new width and height."""
    resized_image_path = os.path.join(os.path.dirname(image_path), f"resized_{os.path.basename(image_path)}")
    with open(image_path, "rb") as image_file:
        image = Image.open(image_file)
        image = image.resize((new_width, new_height))
        image.save(resized_image_path)
    return resized_image_path

def encode_image(image_path):
    """Encode image file to base64."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def is_url_or_filepath(input_string):
    # Check if input_string is a URL
    url_pattern = re.compile(
        r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
    )
    if url_pattern.match(input_string):
        return "URL"

    # Check if input_string is a file path
    file_path = os.path.abspath(input_string)
    if os.path.exists(file_path):
        return "File path"

    return "Invalid"


def extract_data(input_string, data_type):
    # Regular expression to extract content starting from '```python'
    # until the end if there are no closing backticks
    pattern = f"```{data_type}" + r"(.*?)(```|$)"
    # Extract content
    # re.DOTALL allows '.' to match newlines as well
    matches = re.findall(pattern, input_string, re.DOTALL)
    # Return the first match if exists, trimming whitespace and ignoring potential closing backticks
    return matches[0][0].strip() if matches else input_string


def parse_input(code):
    """Use AST to parse the input string and extract the function name, arguments, and keyword arguments."""

    def get_target_names(target):
        """Recursively get all variable names from the assignment target."""
        if isinstance(target, ast.Name):
            return [target.id]
        elif isinstance(target, ast.Tuple):
            names = []
            for elt in target.elts:
                names.extend(get_target_names(elt))
            return names
        return []

    def extract_value(node):
        """提取 AST 节点的实际值"""
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.Name):
            # TODO: a better way to handle variables
            raise ValueError(
                f"Arguments should be a Constant, got a variable {node.id} instead."
            )
        # 添加其他需要处理的 AST 节点类型
        return None

    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                targets = []
                for t in node.targets:
                    targets.extend(get_target_names(t))
                if isinstance(node.value, ast.Call):
                    func_name = node.value.func.id
                    args = [ast.dump(arg) for arg in node.value.args]
                    kwargs = {
                        kw.arg: extract_value(kw.value) for kw in node.value.keywords
                    }
                    print(f"Input: {code.strip()}")
                    print(f"Output Variables: {targets}")
                    print(f"Function Name: {func_name}")
                    print(f"Arguments: {args}")
                    print(f"Keyword Arguments: {kwargs}")
            elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                targets = []
                func_name = extract_value(node.value.func)
                args = [extract_value(arg) for arg in node.value.args]
                kwargs = {kw.arg: extract_value(kw.value) for kw in node.value.keywords}

    except SyntaxError:
        print(f"Input: {code.strip()}")
        print("No match found")

    return targets, func_name, args, kwargs


# Compile a regex pattern to match any Chinese character in the range \u4e00-\u9fff.
def decode_chn(s):
    # If the string contains a literal "\u", decode it.
    if '\\u' in s:
        return s.encode('utf-8').decode('unicode-escape')
    return s


def remove_emojis_and_noise(text):
    # Encode the text to GBK, ignoring characters that can't be encoded
    # Then decode it back to a string
    cleaned_text = text.encode('gbk', 'ignore').decode('gbk')
    return cleaned_text


def resize_down_screenshot(screenshot_path, resized_screenshot_path, max_side_length=1024):
    image = Image.open(screenshot_path)
    width, height = image.size

    # Calculate the new size to maintain aspect ratio
    if width > height:
        new_width = max_side_length
        new_height = int(height * (max_side_length / width))
    elif height > width: # Added check for height > width to avoid issues if width == height
        new_height = max_side_length
        new_width = int(width * (max_side_length / height))
    else: # if width == height and > max_side_length, or already smaller
        if width > max_side_length:
            new_width = max_side_length
            new_height = max_side_length
        else:
            return screenshot_path # No resize needed if already within bounds

    resized_image = image.resize((new_width, new_height))
    resized_image.save(resized_screenshot_path)

    return resized_screenshot_path


# TODO: more robust api key verification, e.g base on choice of `llm_model`

# one available api keys example:
#     api_keys = {
#         "GOOGLE_API_KEY": "AIzaSy",
#         "OPENAI_API_KEY": "sk-proj-6u",
#     }

