.PHONY: build-builder build-image build test clean

# Build the .deb package from source (with patches applied)
build-builder:
	docker build -t nginx-builder -f build/Dockerfile build/

# Build the final runtime image from the .deb
build-image: build-builder
	docker build -t custom-nginx -f Containerfile .

# Shortcut
build: build-image

# Run compatibility tests
test: build-image
	cd test && python3 -m pytest test_compat.py -v

# Cleanup
clean:
	docker rmi nginx-builder custom-nginx 2>/dev/null || true
