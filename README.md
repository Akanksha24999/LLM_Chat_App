# AI Career Guide | Production-Ready LLM Chat App

A full-stack, real-time AI career counseling application powered by Google Gemini-3-flash-preview. This project is designed with a production-grade architecture featuring persistent logging, caching, health monitoring, and automated CI/CD deployment to AWS EC2.


# Features

- AI Career Counseling: Real-time chat integration with Gemini-3-flash-preview for career advice.
- Persistent Chat Logs: Every conversation is stored in PostgreSQL for historical analysis.
- High Performance: Redis integration for session management and caching.
- Reverse Proxy: Nginx handles routing, serving the frontend, and managing WebSocket upgrades.
- Monitoring & Observability: Integrated Prometheus metrics and health check endpoints.
- CI/CD Pipeline: Fully automated testing and deployment to AWS EC2 via GitHub Actions.
- Containerized Architecture: Multi-container orchestration using Docker Compose.


# Tech Stack

- Backend: FastAPI (Python 3.11)
- Frontend: Vanilla HTML5/CSS3/JS (Inter font, Dark mode)
- AI Model: Google Gemini-3-flash-preview
- Database: PostgreSQL 15
- Cache: Redis 7
- Proxy: Nginx
- Monitoring: Prometheus
- DevOps: Docker, GitHub Actions, AWS EC2


# Architecture Overview

The application follows a microservices-inspired containerized architecture:

1.  Nginx: Entry point (Port 80). Routes traffic to the Frontend, Backend APIs, WebSockets, and Metrics.
2.  FastAPI Backend: The core logic. Manages WebSockets, communicates with Gemini API, and handles DB/Cache operations.
3.  PostgreSQL: Stores structured chat logs (session_id, sender, message, timestamp).
4.  Redis: Provides fast in-memory storage for session state and rate-limit handling.
5.  Prometheus: Periodically scrapes the metrics endpoint to monitor application performance.


# CI/CD Pipeline

The project uses GitHub Actions for continuous integration and deployment. The workflow is triggered on every push or pull request to the main branch.

# Workflow Stages:
1.  Test: 
    -   Sets up a Python 3.11 environment.
    -   Installs dependencies.
    -   Runs unit tests using pytest to ensure code quality before building.
2.  Build:
    -   Triggered only if tests pass.
    -   Builds Docker images for both the Backend and Nginx.
    -  Pushes the images to GitHub Container Registry (GHCR).
3.  Deploy:
    -   Triggered only after images are successfully pushed.
    -   Securely transfers configuration files (docker-compose.yml, prometheus.yml) to the AWS EC2 instance.
    -   Connects to the EC2 via SSH, pulls the latest images from GHCR, and restarts the services using Docker Compose.


# Local Development

# Prerequisites
- Docker & Docker Compose installed.
- A Google Gemini API Key (Get one (https://aistudio.google.com/app/apikey)).

# Docker Compose Setup

Follow these steps to get the entire stack running locally using Docker Compose.

1. Clone the Repository
git clone https://github.com/Akanksha24999/LLM_Chat_App
cd LLM_Chat_App

2. Configure Environment Variables
Create a .env file in the root directory and provide your Gemini API key and database credentials.

Variable | Description 
GEMINI_API_KEY: Your Google Gemini API Key.
DB_USER: PostgreSQL Username.
DB_PASSWORD: PostgreSQL Password. 
DB_NAME: PostgreSQL Database Name. 

3. Build and Start Services
Run the following command to build the images and start the containers in detached mode:
docker compose up --build -d

4. Verify the Setup
Once the containers are running, you can access the following services:

Service | URL 
Chat Interface [http://localhost]
Backend Health [http://localhost/health]
Metrics Endpoint [http://localhost/metrics]
Prometheus UI [http://localhost:9090]

5. Managing the Containers
- View Logs: docker compose logs -f
- Stop Services: docker compose stop
- Stop and Remove Containers: docker compose down
- Check Status: docker compose ps


# Deployment (AWS EC2)

The project is configured for automated "Push-to-Deploy" functionality via GitHub Actions.

1. EC2 Instance Setup
- Launch an Ubuntu EC2 instance.
- Allow ports 80 (HTTP), 8000 (API), and 9090 (Prometheus) in Security Groups.
- Install Docker and Docker Compose:
  sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2
  sudo usermod -aG docker $USER && newgrp docker
  mkdir -p ~/app

2. GitHub Secrets Configuration
To enable the CI/CD pipeline, go to Settings > Secrets and variables > Actions in your GitHub repository and add the following secrets:

 Secret | Description 
 GEMINI_API_KEY:  Your Google Gemini API Key. 
 DB_USER:  Database username. 
 DB_PASSWORD:  Database password. 
 DB_NAME:  Database name. 
 EC2_HOST: The Public IP or DNS of your EC2 instance. 
 EC2_USER:  The SSH username for your EC2. 
 EC2_SSH_KEY:  The content of your private key (.pem file). 

3. Execution
# SSL Termination & Security

In this architecture, Nginx acts as an SSL Terminator. This ensures that all communication between the user and the application is encrypted and secure.

How SSL Termination Works:
1. Encrypted Entry: The user's browser connects to Nginx via port 443 (HTTPS). All data, including chat messages, is encrypted between the browser and Nginx.
2. Decryption: Nginx uses the SSL certificate to decrypt the incoming traffic.
3. Internal Routing: Nginx forwards the traffic to the FastAPI Backend over the internal Docker network using standard HTTP/WS. Since this happens inside the private network, it remains secure.
4. Secure WebSockets (WSS): When HTTPS is enabled, the browser requires WebSockets to also be secure (`wss://`). Nginx handles this upgrade seamlessly.

How to Set Up SSL:
1. Obtain Certificates: Generate an SSL certificate and private key for your domain using a free tool like Certbot (Let's Encrypt).
2. Configure Nginx and Docker: 
    - Update nginx.conf to listen on port 443 (HTTPS) using the certificate paths.
    - Expose the certificate files to the Nginx container as a mounted volume in docker-compose.yml.
3. Automate WebSockets: No Python code changes are needed. Nginx decrypts the traffic and passes it internally to FastAPI, while the existing frontend automatically detects the secure connection and switches to Secure WebSockets.


# Health Monitoring & Self-Healing

The application implements a robust health monitoring system to ensure maximum uptime and reliability:

1. The health Endpoint
The FastAPI backend exposes a dedicated health endpoint that performs real-time checks:
- Database Connectivity: Executes a SELECT 1 query to verify PostgreSQL is responsive.
- Redis Connectivity: Sends a PING command to verify Redis is available.
- Response Codes: 
  - 200 OK: All systems are operational.
  - 503 Service Unavailable: One or more dependencies (DB/Redis) are down.

2. Docker Healthchecks
Each service in the docker-compose.yml has a native healthcheck defined:
- Database: Uses pg_isready to ensure it's ready for connections.
- Redis: Uses redis-cli ping for status verification.
- Backend: Usescurl to poll its own healt endpoint.

 3. Service Dependencies
To prevent race conditions, we use condition: service_healthy. The Backend will not start until PostgreSQL and Redis are fully initialized and healthy. Similarly, Nginx waits for the Backend to be healthy before it begins routing traffic.


# Monitoring & Log
View Logs in Database
docker exec -it chat-db psql -U user -d chatdb -c "SELECT * FROM chat_logs ORDER BY timestamp DESC LIMIT 10;"