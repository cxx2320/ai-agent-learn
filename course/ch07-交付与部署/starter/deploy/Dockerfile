# 容器化模板：把管道和它需要的环境一起打包
# 用法（在项目根目录，即含 run.py 的目录）：
#   docker build -f deploy/Dockerfile -t daily-report:0.1 .
#   docker run --rm -v /host/data:/app/data -v /host/out:/app/output daily-report:0.1

FROM python:3.12-slim

# 时区必须显式设置：容器默认 UTC，而业务按站点时区/北京时间思考
ENV TZ=Asia/Shanghai \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONIOENCODING=utf-8

WORKDIR /app

# 先拷依赖清单再装，利用镜像层缓存
COPY requirements.txt* /app/
RUN if [ -f /app/requirements.txt ]; then pip install --no-cache-dir -r /app/requirements.txt; fi

COPY . /app

# 非 root 运行：容器里也用最小权限
RUN useradd -m -u 10001 appuser && chown -R appuser:appuser /app
USER appuser

# 健康检查：容器活着 != 任务成功，所以额外做个轻量探针
HEALTHCHECK --interval=30m --timeout=30s --start-period=10s --retries=2 \
  CMD python -m ops.healthcheck --data-dir /app/data --out-dir /app/output --skip-reconcile || exit 1

ENTRYPOINT ["python", "run.py"]
CMD ["--start", "2026-11-30", "--end", "2026-11-30"]
