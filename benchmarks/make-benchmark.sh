#! /usr/bin/env bash

BASE_DIRECTORY=$(pwd)
# LOG_LEVEL: DEBUG (0) < INFO (1) < WARN (2) < FAIL (3+)
LOG_LEVEL=${LOG_LEVEL:-"INFO"}
# To disable, set COLORED_PROMPT as OFF, otherwise enabled
COLORED_PROMPT=${COLORED_PROMPT:-"ON"}
GREEN=
WHITE=
YELLOW=
RED=
RESET=
if ! [ $COLORED_PROMPT = "OFF" ]; then
    GREEN="\033[0;32m"
    WHITE="\033[0;37m"
    YELLOW="\033[1;33m"
    RED="\033[0;31m"
    RESET="\033[0m"
fi

NOBJ=$NOBJ

function sudoIf () {
    if [ "$(id -u)" -ne 0 ] ; then
        sudo $@
    else
        $@
    fi
}

function get_log_level_integer () {
    local level_string
    local level
    level_string=$(echo $1 | tr 'a-z', 'A-Z')
    case $level_string in
    "DEBUG") level=0;;
    "INFO") level=1;;
    "WARN") level=2;;
    "FAIL") level=3;;
    esac
    return $level
}

function log () {
    local log_level
    local level_string
    local message_level
    
    get_log_level_integer $LOG_LEVEL
    log_level=$?

    level_string=$(echo $1 | tr 'a-z', 'A-Z')
    get_log_level_integer $level_string
    message_level=$?

    if [ $message_level -ge $log_level ]; then
        case $message_level in
        "0") echo -e $GREEN[DEBUG]$RESET $2;;
        "1") echo -e $WHITE[INFO]$RESET $2;;
        "2") echo -e $YELLOW[WARN]$RESET $2;;
        "3") echo -e $RED[FAIL]$RESET $2;;
        esac
    fi
}

function install_dependencies () {
    sudoIf apt-get update
    sudoIf apt-get install automake
}


function download_source_tgz () {
    if [ -d "$1" ]; then
        log INFO "Already downloaded: $1"
        return 0
    fi
    curl -sk $2 | tar xz
    if ! [ -d "$1" ]; then
        log FAIL "Download failed: $1"
        return 1
    fi
}

function download_source_txz () {
    if [ -d "$1" ]; then
        log INFO "Already downloaded: $1"
        return 0
    fi
    curl -sk $2 | tar xJ
    if ! [ -d "$1" ]; then
        log FAIL "Download failed: $1"
        return 1
    fi
}

function build_gcov_obj () {
    if [ -f "$1/$2" ]; then 
        log INFO "Gcov object already built: $1/$2"
        return 0
    fi
    mkdir -p $1
    cd $1
    ../configure --disable-nls CFLAGS="-g -fprofile-arcs -ftest-coverage" > /dev/null && make > /dev/null
    cd ..
    if ! [ -f "$1/$2" ]; then 
        return 1
    fi
}

function build_multiple_gcov_obj () {
    if [ "$NOBJ" = "" ] ; then
        build_gcov_obj $1 $2
        return $?
    fi

    for i in $(seq 1 $NOBJ) ; do
        build_gcov_obj $1$i $2
    done
}

function build_llvm_obj () {
    local base_dir
    base_dir=$(pwd)
    if [ -f "$1/$2" ]; then 
        log INFO "LLVM object already built: $1/$2"
        return 0
    fi
    mkdir -p $1
    cd $1
    LLVM_COMPILER=clang CC=wllvm ../configure --disable-nls CFLAGS="-g -O1 -Xclang -disable-llvm-passes -D__NO_STRING_INLINES  -D_FORTIFY_SOURCE=0 -U__OPTIMIZE__" > /dev/null && \
    LLVM_COMPILER=clang make > /dev/null
    if [ $? -ne 0 ]; then
        return 1
    fi
    if ! [ -z $3 ]; then 
        cd $3
    fi
    find . -executable -type f | xargs -I '{}' extract-bc '{}'
    cd $base_dir
    if ! [ -f "$1/$2" ]; then
        return 1
    fi
}

function build_multiple_llvm_obj () {
    local retcode
    build_llvm_obj $1 $2 $3
    retcode=$?
    # if [ "$NOBJ" = "" ] ; then
    return $retcode
}

function build_gawk-5.1.0 () {
    cd $BASE_DIRECTORY
    log INFO "Downloading: gawk-5.1.0"
    download_source_tgz gawk-5.1.0 https://ftp.gnu.org/gnu/gawk/gawk-5.1.0.tar.gz
    downloaded=$?
    if [ $downloaded -ne 0 ]; then
        log FAIL "Failed to build gawk-5.1.0"
        return 1
    fi

    cd $BASE_DIRECTORY/gawk-5.1.0
    log INFO "Build gcov object: gawk-5.1.0"
    build_multiple_gcov_obj obj-gcov gawk
    if [ $? -ne 0 ] ; then
        log FAIL "Failed to build gcov object: gawk-5.1.0"
    fi

    cd $BASE_DIRECTORY/gawk-5.1.0
    log INFO "Build LLVM object: gawk-5.1.0"
    build_multiple_llvm_obj obj-llvm gawk.bc
    if [ $? -ne 0 ] ; then
        log FAIL "Failed to build LLVM object: gawk-5.1.0"
    fi
    log INFO "Build process finished: gawk-5.1.0"
}

function build_gcal-4.1 () {
    cd $BASE_DIRECTORY
    log INFO "Downloading: gcal-4.1"
    download_source_tgz gcal-4.1 https://ftp.gnu.org/gnu/gcal/gcal-4.1.tar.gz
    downloaded=$?
    if [ $downloaded -ne 0 ]; then
        log FAIL "Failed to build gcal-4.1"
        return 1
    fi

    cd $BASE_DIRECTORY/gcal-4.1
    log INFO "Build gcov object: gcal-4.1"
    build_multiple_gcov_obj obj-gcov src/gcal
    if [ $? -ne 0 ] ; then
        log FAIL "Failed to build gcov object: gcal-4.1"
    fi

    cd $BASE_DIRECTORY/gcal-4.1
    log INFO "Build LLVM object: gcal-4.1"
    build_multiple_llvm_obj obj-llvm src/gcal.bc src
    if [ $? -ne 0 ] ; then
        log FAIL "Failed to build LLVM object: gcal-4.1"
    fi
    log INFO "Build process finished: gcal-4.1"
}

function build_find-4.7.0 () {
    cd $BASE_DIRECTORY
    log INFO "Downloading: find-4.7.0"
    download_source_txz findutils-4.7.0 https://ftp.gnu.org/gnu/findutils/findutils-4.7.0.tar.xz
    downloaded=$?
    if [ $downloaded -ne 0 ]; then
        log FAIL "Failed to build find-4.7.0"
        return 1
    fi

    cd $BASE_DIRECTORY/findutils-4.7.0
    log INFO "Build gcov object: find-4.7.0"
    build_multiple_gcov_obj obj-gcov find/find
    if [ $? -ne 0 ] ; then
        log FAIL "Failed to build gcov object: find-4.7.0"
    fi

    cd $BASE_DIRECTORY/findutils-4.7.0
    log INFO "Build LLVM object: find-4.7.0"
    build_multiple_llvm_obj obj-llvm find/find.bc find
    if [ $? -ne 0 ] ; then
        log FAIL "Failed to build LLVM object: find-4.7.0"
    fi
    log INFO "Build process finished: find-4.7.0"
}

function build_sed-4.8 () {
    cd $BASE_DIRECTORY
    log INFO "Downloading: sed-4.8"
    download_source_txz sed-4.8 https://ftp.gnu.org/gnu/sed/sed-4.8.tar.xz
    downloaded=$?
    if [ $downloaded -ne 0 ]; then
        log FAIL "Failed to build sed-4.8"
        return 1
    fi

    cd $BASE_DIRECTORY/sed-4.8
    log INFO "Build gcov object: sed-4.8"
    build_multiple_gcov_obj obj-gcov sed/sed
    if [ $? -ne 0 ] ; then
        log FAIL "Failed to build gcov object: sed-4.8"
    fi

    cd $BASE_DIRECTORY/sed-4.8
    log INFO "Build LLVM object: sed-4.8"
    build_multiple_llvm_obj obj-llvm sed/sed.bc sed
    if [ $? -ne 0 ] ; then
        log FAIL "Failed to build LLVM object: sed-4.8"
    fi
    log INFO "Build process finished: sed-4.8"
}


function build_grep-3.6 () {
    cd $BASE_DIRECTORY
    log INFO "Downloading: grep-3.6"
    download_source_txz grep-3.6 https://ftp.gnu.org/gnu/grep/grep-3.6.tar.xz
    downloaded=$?
    if [ $downloaded -ne 0 ]; then
        log FAIL "Failed to build grep-3.6"
        return 1
    fi

    cd $BASE_DIRECTORY/grep-3.6
    log INFO "Build gcov object: grep-3.6"
    build_multiple_gcov_obj obj-gcov src/grep
    if [ $? -ne 0 ] ; then
        log FAIL "Failed to build gcov object: grep-3.6"
    fi

    cd $BASE_DIRECTORY/grep-3.6
    log INFO "Build LLVM object: grep-3.6"
    build_multiple_llvm_obj obj-llvm src/grep.bc src
    if [ $? -ne 0 ] ; then
        log FAIL "Failed to build LLVM object: grep-3.6"
    fi
    log INFO "Build process finished: grep-3.6"
}

function build_diff-3.7 () {
    cd $BASE_DIRECTORY
    log INFO "Downloading: diffutils-3.7"
    download_source_txz diffutils-3.7 https://ftp.gnu.org/gnu/diffutils/diffutils-3.7.tar.xz
    downloaded=$?
    if [ $downloaded -ne 0 ]; then
        log FAIL "Failed to build diffutils-3.7"
        return 1
    fi

    cd $BASE_DIRECTORY/diffutils-3.7
    log INFO "Build gcov object: diff-3.7"
    build_multiple_gcov_obj obj-gcov src/diff
    if [ $? -ne 0 ] ; then
        log FAIL "Failed to build gcov object: diff-3.7"
    fi

    cd $BASE_DIRECTORY/diffutils-3.7
    log INFO "Build LLVM object: diff-3.7"
    build_multiple_llvm_obj obj-llvm src/diff.bc src
    if [ $? -ne 0 ] ; then
        log FAIL "Failed to build LLVM object: diff-3.7"
    fi
    log INFO "Build process finished: diff-3.7"
}


function help () {
    cat <<-EOF
Usage: $0 [-h|--help] [-l|--list] [--n-objs INT]
        <benchmark> [<benchmark> ...]
Optional arguments:
    -h, --help      Print this list
    -l, --list      List benchmarks
        --n-objs INT
                    Build multiple objects
        
Positional arguments:
    <benchmark>     The name of benchmark, see the supported list
                    with --list option
EOF
}

function list () {
    cat <<-EOF
Benchmark lists
    gawk-5.1.0
    gcal-4.1
    find-4.7.0      findutils-4.7.0
    sed-4.8
    grep-3.6
    diff-3.7        diffutils-3.7
    all             download and build all
EOF
}


function build () {
    case $1 in
    "gawk-5.1.0") build_gawk-5.1.0;;
    "gcal-4.1") build_gcal-4.1;;
    "find-4.7.0") build_find-4.7.0;;
    "grep-3.6") build_grep-3.6;;
    "diff-3.7") build_diff-3.7;;
    "sed-4.8") build_sed-4.8;;
    *) log WARN "Unknown benchmark: $1";;
    esac
}

if [ -z "$1" ] ; then
    help
    exit 1
fi

if [ "$1" = "-h" ] || [ "$1" = "--help" ] ; then
    help
    exit 0
fi

if [ "$1" = "-l" ] || [ "$1" = "--list" ] ; then
    list
    exit 0
fi

if [ "$1" = "--n-objs" ] ; then
    NOBJ=$2
    shift
    shift
fi

if [ "$1" = "all" ] ; then
    benchmarks="gawk-5.1.0 gcal-4.1 find-4.7.0 grep-3.6 diff-3.7 sed-4.8"
else
    benchmarks=$@
fi

for benchmark in $benchmarks; do
    build $benchmark
done
