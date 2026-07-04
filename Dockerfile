FROM python:3.10-slim

# 系统依赖：中文字体 + cv2 headless 所需 libGL 替代
RUN sed -i 's|http://deb.debian.org|https://mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update && apt-get install -y --no-install-recommends \
        fonts-noto-cjk \
        libglib2.0-0 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先复制依赖文件，利用 Docker 层缓存
COPY requirements.txt .
RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt

# 复制项目代码和资源
COPY src/        src/
COPY templates/  templates/
COPY meta.json   meta.json
COPY gif.json    gif.json

# output 目录运行时生成
RUN mkdir -p output

# 环境变量默认值（可被 docker run -e 或 .env 挂载覆盖）
ENV MEME_FONT=/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc \
    PYTHONUNBUFFERED=1

COPY server.py .

EXPOSE 8000

# HTTP 服务模式（默认）；CLI 调试可用：
#   docker run --rm -v $(pwd)/output:/app/output --entrypoint python ptop main.py input.png gif
CMD ["uvicorn", "server:server", "--host", "0.0.0.0", "--port", "8000"]
