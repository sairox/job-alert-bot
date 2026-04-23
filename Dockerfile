# AWS Lambda container image with Playwright + Chromium
# Force x86_64 so it matches the Lambda architecture setting in Terraform.
# This also avoids the dnf/microdnf mismatch on Apple Silicon Macs.
#
# Build:  docker build --platform linux/amd64 -t job-alert-bot .
# Push:   docker tag job-alert-bot:latest <account>.dkr.ecr.<region>.amazonaws.com/job-alert-bot:latest
#         docker push <account>.dkr.ecr.<region>.amazonaws.com/job-alert-bot:latest

FROM --platform=linux/amd64 python:3.12-slim

ENV LAMBDA_TASK_ROOT=/var/task
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
WORKDIR ${LAMBDA_TASK_ROOT}

RUN pip install --no-cache-dir awslambdaric

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN playwright install --with-deps chromium

COPY src/ ${LAMBDA_TASK_ROOT}/src/

ENTRYPOINT ["python", "-m", "awslambdaric"]
CMD ["src.main.lambda_handler"]

