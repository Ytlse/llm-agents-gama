# Makefile for Docker Compose commands

# Default target
up:
	@echo "Starting all services..."
	docker compose up -d

# Stop and remove containers, networks, volumes, and images
down:
	@echo "Stopping and removing containers, networks, volumes, and images..."
	docker compose down --rmi all

# Clean up everything (including volumes)
clean:
	@echo "Cleaning up everything..."
	docker compose down -v --rmi all
	docker system prune -a --volumes -f

# Rebuild images and restart containers
rebuild:
	@echo "Rebuilding images and restarting containers..."
	docker compose build --no-cache
	docker compose up -d

# View logs
logs:
	@echo "Viewing logs..."
	docker compose logs -f

# Restart all services
restart:
	@echo "Restarting all services..."
	docker compose restart

# List all running containers
ps:
	@echo "Listing running containers..."
	docker compose ps

# Check the status of services
status:
	@echo "Checking service status..."
	docker compose ps

# Execute a command in a running container
exec-%:
	@echo "Executing command in container $*..."
	docker compose exec $(container) $(command)

.PHONY: up down clean rebuild logs restart ps status exec