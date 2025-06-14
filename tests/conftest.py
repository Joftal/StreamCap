import os
import sys
from pathlib import Path

# 获取项目根目录
root_dir = Path(__file__).parent.parent

# 将项目根目录添加到 Python 路径
sys.path.insert(0, str(root_dir))

# 设置测试环境变量
os.environ["TESTING"] = "true" 