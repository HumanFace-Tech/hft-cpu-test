#!/usr/bin/env bash
#
# Optional helper to build multiple llama.cpp variants
# This is NOT required - you can build manually and just reference paths in YAML

set -euo pipefail

# Configuration
LLAMA_CPP_REPO="${LLAMA_CPP_REPO:-https://github.com/ggerganov/llama.cpp.git}"
LLAMA_CPP_COMMIT="${LLAMA_CPP_COMMIT:-master}"
BUILD_BASE_DIR="${BUILD_BASE_DIR:-$(pwd)/builds}"
JOBS="${JOBS:-$(nproc)}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}🔨 HFT CPU Build Setup${NC}"
echo "This will create multiple llama.cpp builds in: $BUILD_BASE_DIR"
echo ""

# Ensure build dir exists
mkdir -p "$BUILD_BASE_DIR"

# Clone or update llama.cpp
LLAMA_SRC="$BUILD_BASE_DIR/llama.cpp-src"
if [ ! -d "$LLAMA_SRC" ]; then
    echo -e "${GREEN}📦 Cloning llama.cpp...${NC}"
    git clone "$LLAMA_CPP_REPO" "$LLAMA_SRC"
    cd "$LLAMA_SRC"
    git checkout "$LLAMA_CPP_COMMIT"
else
    echo -e "${GREEN}📦 Updating llama.cpp...${NC}"
    cd "$LLAMA_SRC"
    git fetch
    git checkout "$LLAMA_CPP_COMMIT"
fi

COMMIT_HASH=$(git rev-parse --short HEAD)
echo -e "Commit: $COMMIT_HASH"
echo ""

# Build function
build_variant() {
    local name=$1
    local cmake_args=$2
    local env_vars=${3:-}
    
    echo -e "${GREEN}🔨 Building: $name${NC}"
    
    local build_dir="$BUILD_BASE_DIR/$name"
    mkdir -p "$build_dir"
    
    # Create manifest
    cat > "$build_dir/manifest.json" <<EOF
{
  "name": "$name",
  "commit": "$COMMIT_HASH",
  "date": "$(date -Iseconds)",
  "cmake_args": "$cmake_args",
  "env": "$env_vars"
}
EOF
    
    # Build
    cd "$LLAMA_SRC"
    rm -rf build
    mkdir build
    cd build
    
    if [ -n "$env_vars" ]; then
        eval "$env_vars cmake $cmake_args .."
    else
        cmake $cmake_args ..
    fi
    
    cmake --build . --config Release -j "$JOBS" --target llama-bench
    
    # Copy binary
    cp bin/llama-bench "$build_dir/"
    
    echo -e "${GREEN}✓ $name built${NC}"
    echo ""
}

# Build variants
echo -e "${YELLOW}Building variants...${NC}"
echo ""

# 1. CPU-only (pure fallback)
build_variant "cpu-only-znver1" \
    "-DCMAKE_BUILD_TYPE=Release -DCMAKE_C_FLAGS='-march=znver1' -DCMAKE_CXX_FLAGS='-march=znver1' -DGGML_BLAS=OFF"

# 2. OpenBLAS
if command -v pkg-config &> /dev/null && pkg-config --exists openblas; then
    build_variant "openblas-znver1" \
        "-DCMAKE_BUILD_TYPE=Release -DCMAKE_C_FLAGS='-march=znver1' -DCMAKE_CXX_FLAGS='-march=znver1' -DGGML_BLAS=ON -DGGML_BLAS_VENDOR=OpenBLAS"
else
    echo -e "${YELLOW}⚠️  OpenBLAS not found, skipping${NC}"
fi

# 3. BLIS with OpenMP
if [ -d "/usr/include/blis" ] || [ -d "/usr/local/include/blis" ]; then
    build_variant "blis-omp-znver1" \
        "-DCMAKE_BUILD_TYPE=Release -DCMAKE_C_FLAGS='-march=znver1' -DCMAKE_CXX_FLAGS='-march=znver1' -DGGML_BLAS=ON -DGGML_BLAS_VENDOR=FLAME"
else
    echo -e "${YELLOW}⚠️  BLIS not found, skipping${NC}"
fi

# 4. MKL (if available)
if [ -d "/opt/intel/oneapi/mkl" ]; then
    build_variant "mkl-znver1" \
        "-DCMAKE_BUILD_TYPE=Release -DCMAKE_C_FLAGS='-march=znver1' -DCMAKE_CXX_FLAGS='-march=znver1' -DGGML_BLAS=ON -DGGML_BLAS_VENDOR=Intel10_64lp" \
        "source /opt/intel/oneapi/setvars.sh &&"
else
    echo -e "${YELLOW}⚠️  MKL not found, skipping${NC}"
fi

echo -e "${GREEN}✅ All builds complete!${NC}"
echo ""
echo "Build directory: $BUILD_BASE_DIR"
echo ""
echo "Update your YAML configs with these paths:"
ls -1d "$BUILD_BASE_DIR"/*/llama-bench | while read -r path; do
    echo "  - path: $path"
done
