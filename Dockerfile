# AWS Lambda container image with Playwright + Chromium
# Force x86_64 so it matches the Lambda architecture setting in Terraform.
# This also avoids the dnf/microdnf mismatch on Apple Silicon Macs.
#
# Build:  docker build --platform linux/amd64 -t job-alert-bot .
# Push:   docker tag job-alert-bot:latest <account>.dkr.ecr.<region>.amazonaws.com/job-alert-bot:latest
#         docker push <account>.dkr.ecr.<region>.amazonaws.com/job-alert-bot:latest

FROM --platform=linux/amd64 public.ecr.aws/lambda/python:3.12

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Chromium + all required system dependencies in one step.
# --with-deps lets Playwright handle OS package detection automatically.
RUN playwright install --with-deps chromium

COPY src/ ${LAMBDA_TASK_ROOT}/src/

CMD ["src.main.lambda_handler"]
