.PHONY: build-builder build-image build test clean

TAG := $(shell date +%Y%m%d-%H%M%S)

# Build the .deb package from source (with patches applied)
build-builder:
	docker build -t nginx-builder -f build/Dockerfile build/

# Build the final runtime image from the .deb
build-image: build-builder
	docker build -t custom-nginx:$(TAG) -t custom-nginx:latest --label build-time=$(TAG) -f Containerfile .

# Shortcut
build: build-image

# Run compatibility tests
test:
	cd test && python3 -m pytest test_nginx.py -v

# Cleanup
clean:
	docker rmi -f nginx-builder $$(docker images -q custom-nginx) 2>/dev/null || true
