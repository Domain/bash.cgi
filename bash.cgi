#!/bin/bash
# Author: (c) Colas Nahaboo http://colas.nahaboo.net with a MIT License.
# See https://github.com/ColasNahaboo/cgibashopts
# Author: (c) Domain https://github.com/Domain with a MIT License.
# See https://github.com/Domain/bash.cgi
# Uses the CGI env variables REQUEST_METHOD CONTENT_TYPE QUERY_STRING

export BASHCGI_RELEASE=5.0.0
export BASHCGI_VERSION="${BASHCGI_RELEASE%%.*}"

declare cr=$'\r'
declare nl=$'\n'
declare response_content_type=''
declare -A FORMS
declare -A COOKIES
declare -A SET_COOKIES
export FORMFILES=
export FORMQUERY=

export BASHCGI_DIR="${BASHCGI_ROOT:-${TMPDIR:-/tmp}}/bash.cgi.dir"
BASHCGI_TMP="$BASHCGI_DIR/tmp"
BASHCGI_UPLOAD="$BASHCGI_DIR/upload"
BASHCGI_SESSION="$BASHCGI_DIR/session"

mkdir -p "$BASHCGI_DIR" > /dev/null 2>&1

bashcgi_clean() {
    [ -f "$BASHCGI_TMP" ] && rm -rf "$BASHCGI_TMP"
}

overtrap() {
    local handler="$1"
    shift
    local signals=$@
    for sig in "${signals[@]}"; do
        local cur="$(trap -p $sig | sed -nr "s/trap -- '(.*)' $sig\$/\1/p")"
        if test ${cur:+x}; then
            trap "{ $cur; }; { $handler; }" $sig
        else
            trap "$handler" $sig
        fi
    done
}

overtrap bashcgi_clean EXIT

trace() {
    [ -v "$BASHCGI_DEBUG" ] && { echo "$@" >> ${BASHCGI_DIR:-/tmp}/out.log; }
}

# decodes the %XX url encoding in $1, same as urlencode -d but faster
# removes carriage returns to force unix newlines, converts + into space
urldecode() {
    local v="${1//+/ }" d r=''
    while [ -n "$v" ]; do
        if [[ $v =~ ^([^%]*)%([0-9a-fA-F][0-9a-fA-F])(.*)$ ]]; then
            eval d="\$'\x${BASH_REMATCH[2]}'"
            [ "$d" = "$cr" ] && d=
            r="$r${BASH_REMATCH[1]}$d"
            v="${BASH_REMATCH[3]}"
        else
            r="$r$v"
            break
        fi
    done
    echo "$r"
}

# the reverse of urldecode above
urlencode() {
    local length="${#1}" i c
    for ((i = 0; i < length; i++)); do
        c="${1:i:1}"
        case $c in
            [a-zA-Z0-9.~_-]) echo -n "$c" ;;
            *) printf '%%%02X' "'$c" ;;
        esac
    done
}

handle_upload() {
    if [[ ${CONTENT_TYPE:-} =~ ^multipart/form-data\;[[:space:]]*boundary=([^\;]+) ]]; then
        local sep="--${BASH_REMATCH[1]}"
        local OIFS="$IFS"
        IFS=$'\r'
        while read -r line; do
            if [[ $line =~ ^Content-Disposition:\ *form-data\;\ *name=\"([^\"]+)\"(\;\ *filename=\"([^\"]+)\")? ]]; then
                local var="${BASH_REMATCH[1]}"
                local val="${BASH_REMATCH[3]}"
                [[ $val =~ [%+] ]] && val=$(urldecode "$val")
                local type=
                read -r line
                while [ -n "$line" ]; do
                    if [[ $line =~ ^Content-Type:\ *text/plain ]]; then
                        type=txt
                    elif [[ $line =~ ^Content-Type: ]]; then # any other type
                        type=bin
                    fi
                    read -r line
                done
                if [ "$type" = bin ]; then # binary file upload
                    # binary-read stdin till next step
                    sed -n -e "{:loop p; n;/^$sep/q; b loop}" >$BASHCGI_TMP
                    [ $BASHCGI_TMP != /dev/null ] &&
                        truncate -s -2 $BASHCGI_TMP # remove last \r\n
                elif [ "$type" = txt ]; then        # text file upload
                    local lp=
                    while read -r line; do
                        [[ $line =~ ^"$sep" ]] && break
                        echo -n "$lp$line"
                        lp="$nl"
                    done >$BASHCGI_TMP
                else # string, possibly multi-line
                    val=
                    while read -r line; do
                        [[ $line =~ ^"$sep" ]] && break
                        val="$val${val:+$nl}${line}"
                    done
                fi
                if [ -n "$type" ]; then
                    if [ $BASHCGI_TMP != /dev/null ]; then
                        if [ -n "$val" ]; then
                            # a file was uploaded, even empty
                            [ -n "$FORMFILES" ] || mkdir -p "$BASHCGI_UPLOAD"
                            FORMFILES="$FORMFILES${FORMFILES:+ }$var"
                            declare -x "FORMFILE_$var=$BASHCGI_UPLOAD/${var}"
                            mv $BASHCGI_TMP "$BASHCGI_UPLOAD/${var}"
                        else
                            rm -f $BASHCGI_TMP
                        fi
                    fi
                fi
                FORMS["$var"]="$val"
            fi
        done
        IFS="$OIFS"
        return 0
    fi

    return 1
}

extract() {
    declare -n aa="$1"
    shift
    local s="$@"
    trace "Extracting $s ..."
    while [[ $s =~ ^([^=]*)=([^\&\;]*)[\;\&]*(.*)$ ]]; do
        local var="$(echo "${BASH_REMATCH[1]}" | xargs)"
        local val="$(echo "${BASH_REMATCH[2]}" | xargs)"
        s="${BASH_REMATCH[3]}"
        [[ $val =~ [%+] ]] && val=$(urldecode "$val")
        aa["$var"]="$val"
        trace "Found key '$var', value '$val'"
    done
}

parse_request() {
    local s=""
    if [ "${REQUEST_METHOD:-}" = POST ]; then
        trace "Found POST"
        handle_upload && s="${QUERY_STRING:-}" || s="$(cat)&${QUERY_STRING:-}"
    else
        trace "POST not found"
        s="${QUERY_STRING:-}"
    fi

    # regular (no file uploads) arguments processing
    if [[ $s =~ = ]]; then # modern & (or ;) separated list of key=value
        extract FORMS "$s"
    else # legacy indexed search
        FORMQUERY=$(urldecode "$s")
    fi
}

parse_cookies() {
    trace "Parsing cookies ... '${HTTP_COOKIE:-}'"
    extract COOKIES "${HTTP_COOKIE:-}"
}

set_cookie() {
    local key="$1"
    shift
    local value="$*"

    SET_COOKIES["$key"]="$value"
}

content_type()
{
    [ $# -eq 1 ] || return 1
    [ -z "${response_content_type}" ] || return 2
    
    response_content_type=$1

    for k in "${!SET_COOKIES[@]}"; do
        echo "Set-Cookie: $k=${SET_COOKIES[$k]}"
    done

    echo "Content-Type: $1; charset=utf-8"
    echo "Cache-Control: no-cache"
    echo "Content-range: bytes */*" # this prevent mod_deflate buffering
    echo
}

date2stamp () {
    date --date "$1" +%s
}

stamp2date (){
    date --date @$1 "+%Y-%m-%d %T"
}

dateDiff (){
    declare -i sec=86400
    case $1 in
        -s)   sec=1;      shift;;
        -m)   sec=60;     shift;;
        -h)   sec=3600;   shift;;
        -d)   sec=86400;  shift;;
        *)    sec=86400;;
    esac
    local date1=$(date2stamp "$1")
    local date2=$(date2stamp "$2")
    local diffSec=$((date2-date1))
    echo $((diffSec/sec))
}

new_session() {
    local sid=$(cat /proc/sys/kernel/random/uuid)
    local sfile="$BASHCGI_SESSION/$sid"
    mkdir -p "$BASHCGI_SESSION"
    touch "$sfile"
    trace "new session $sid in $BASHCGI_SESSION"

    local expired=${1:-$(date -d "now 1 month" "+%Y-%m-%d %T")}
    echo "declare -x bashcgi_expired=\"$expired\"" >> "$sfile"
    echo "$sid"
}

check_session() {
    local sid="$1"
    local sfile="$BASHCGI_SESSION/$sid"
    trace "checking session file $sfile ..."
    [ -f "$sfile" ] && source "$sfile" || { trace "fail to load $sfile"; return -1; }
    trace "checking expired date $bashcgi_expired ..."
    [ -n "$bashcgi_expired" ] && [ $(dateDiff -s "now" "$bashcgi_expired") -gt 0 ] || 
        { rm -rf "$sfile"; trace "session expired at $bashcgi_expired"; return -2; }

    shift
    local keys="$@"
    declare -i i=1
    for k in "$@"; do
        [ -n "${!k}" ] && trace "key $k=${!k} confirmed" || { trace "missing key $k"; return i; }
        ((i++))
    done
    trace "session $sid is ok"
}

save_session() {
    trace "saving session $#: '$@'"
    check_session $1 && trace "check passed" || { trace "fail to save session"; return 1; }

    local sid="$1"
    local sfile="$BASHCGI_SESSION/$sid"

    shift
    for v in "$@"; do
        echo "$v" >> "$sfile"
    done
}

delete_session() {
    local sid="$1"
    local sfile="$BASHCGI_SESSION/$sid" 
    rm -rf "$sfile"
}

parse_request
parse_cookies
