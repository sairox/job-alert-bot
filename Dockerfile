# AWS Lambda container image with Playwright + Chromium
# Build:  docker build -t job-alert-bot .
# Push:   docker tag job-alert-bot <account>.dkr.ecr.<region>.amazonaws.com/job-alert-bot:latest
#         docker push <account>.dkr.ecr.<region>.amazonaws.com/job-alert-bot:latest

FROM public.ecr.aws/lambda/python:3.11

# System dependencies required by Chromium
RUN dnf install -y \
    atk \
    cups-libs \
    gtk3 \
    libXcomposite \
    libXcursor \
    libXdamage \
    libXext \
    libXi \
    libXrandr \
    libXScrnSaver \
    libXtst \
    pango \
    xorg-x11-fonts-100dpi \
    xorg-x11-fonts-75dpi \
    xorg-x11-fonts-cyrillic \
    xorg-x11-fonts-misc \
    xorg-x11-fonts-Type1 \
    xorg-x11-utils \
    alsa-lib \
    nss \
    mesa-libgbm \
    && dnf clean all

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download Playwright's bundled Chromium
RUN playwright install chromium

COPY src/ ${LAMBDA_TASK_ROOT}/src/

CMD ["src.main.lambda_handler"]
