# Use an official Python runtime as a parent image
FROM ubuntu:20.04

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    libmysqlclient-dev \
    libssl-dev \
    libffi-dev \
    build-essential \
    curl
    
# Set the working directory to /app
WORKDIR /app

# Copy the current directory contents into the container at /app
# Copy the poetry files and install dependencies
COPY pyproject.toml poetry.lock /app/
RUN apt-get update && \
    apt-get install -y curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:${PATH}"

# Copy the project code
COPY tailoredscoop /app/tailoredscoop

RUN poetry install --no-dev

# Copy the scripts code
COPY scripts /app/scripts
RUN chmod +x /app/scripts/today_story.py
RUN chmod +x /app/scripts/top_stories.py

# Set the environment variables
ENV OPENAI_API_KEY=your_openai_api_key \
    NEWSAPI_API_KEY=your_newsapi_api_key \
    MYSQL_USERNAME=csong \
    MYSQL_PASSWORD=your_mysql_password \
    MYSQL_HOST=54.210.64.57 \
    MYSQL_DATABASE=apps \
    SENDGRID_API_KEY=your_sendgrid_api_key \
    MONGODB_URL=your_mongodb_url

RUN ln -s /usr/bin/python3 /usr/bin/python

# Set the entrypoint to run the scripts
# CMD ["python", "scripts/today_story.py", "&&", "python", "scripts/top_stories.py"]
ENTRYPOINT ["poetry", "run"]
CMD ["sh", "-c", "python scripts/today_story.py && python scripts/top_stories.py"]