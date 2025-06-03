# 使用官方 Python 3.9 精简版镜像作为基础镜像
FROM python:3.9-slim

# 设置容器内的工作目录为 /app
WORKDIR /app

# 将当前目录内容复制到容器内的 /app
COPY . /app

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 对外暴露 5000 端口
EXPOSE 5000

# 设置环境变量，指定 Flask 启动入口
ENV FLASK_APP=app.py

# 容器启动时运行 Flask 应用
CMD ["python", "app.py"]

