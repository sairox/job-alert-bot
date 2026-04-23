# Use Debian-slim instead of the Lambda-specific base image.
# Reasons:
#   - Playwright officially supports Debian/Ubuntu and uses apt-get correctly
#   - Lambda base images (AL2/AL2023) are not recognised by Playwright's --with-deps
#   - awslambdaric (installed below) provides the Lambda runtime bridge
#
# Build:  docker build --platform linux/amd64 -t job-alert-bot .
# Push:   docker tag job-alert-bot:latest <account>.dkr.ecr.<region>.amazonaws.com/job-alert-bot:latest
#         docker push <account>.dkr.ecr.<region>.amazonaws.com/job-alert-bot:latest

FROM --platform=linux/amd64 python:3.12-slim

# Lambda task root — mirrors the Lambda execution environment
ENV LAMBDA_TASK_ROOT=/var/task
# Fix Playwright browser path: Lambda runs as an unpredictable user so we pin
# the browsers to a fixed directory that any user can read.
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
WORKDIR ${LAMBDA_TASK_ROOT}

# Lambda Runtime Interface Client — bridges Debian container with Lambda
RUN pip install --no-cache-dir awslambdaric

# Install app dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Chromium + all system dependencies.
# Playwright recognises Debian and uses apt-get correctly here.
RUN playwright install --with-deps chromium

# Copy source code
COPY src/ ${LAMBDA_TASK_ROOT}/src/

# awslambdaric handles the Lambda invoke protocol;
# CMD specifies the handler as module.function
ENTRYPOINT ["python", "-m", "awslambdaric"]
CMD ["src.main.lambda_handler"]
