#!/usr/bin/env bash
# Build and verify MVP. Run from anywhere; optionally set ANDROID_JAVA_HOME.
set -euo pipefail
cd "$(dirname "$0")/../android"
if [ -n "${ANDROID_JAVA_HOME:-}" ]; then
    export JAVA_HOME="$ANDROID_JAVA_HOME"
elif [ -d /Library/Java/JavaVirtualMachines/temurin-22.jdk/Contents/Home ]; then
    export JAVA_HOME=/Library/Java/JavaVirtualMachines/temurin-22.jdk/Contents/Home
fi
./gradlew :app:assembleDebug :app:testDebugUnitTest :data:testDebugUnitTest :domain:testDebugUnitTest :app:lintDebug --console=plain "$@"
