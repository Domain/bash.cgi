#!/bin/bash
# Author: (c) Colas Nahaboo http://colas.nahaboo.net with a MIT License.
# See https://github.com/ColasNahaboo/bashcgi
# Uses the CGI env variables REQUEST_METHOD CONTENT_TYPE QUERY_STRING

export BASHCGI_RELEASE=5.0.0
export BASHCGI_VERSION="${BASHCGI_RELEASE%%.*}"
declare cr=$'\r'
declare nl=$'\n'
declare -A FORMS
declare -A COOKIES
export FORMFILES=
export FORMQUERY=

# parse options
uploads=true
tmpfs=${TMPDIR:-/tmp}
OPTIONS='nd:'
OPTIND=1
while getopts "${OPTIONS}" _o; do
    case "$_o" in
    n) uploads=false ;;
    d) tmpfs="$OPTARG" ;;
    *)
        echo "unknown option: $_o"
        exit 1
        ;;
    esac
done
shift $((OPTIND - 1))

if "$uploads"; then
    export BASHCGI_DIR="$tmpfs/bashcgi-files.$$"
    BASHCGI_TMP="$BASHCGI_DIR.tmp"
    bashcgi_clean() {
        [ -n "$BASHCGI_DIR" ] && [ -d "$BASHCGI_DIR" ] && rm -rf "$BASHCGI_DIR"
    }
    trap bashcgi_clean EXIT
else
    BASHCGI_TMP=/dev/null
fi

trace() {
    #echo "$@" >> ${TMPDIR:-/tmp}/out.log
    :
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
                            [ -n "$FORMFILES" ] || mkdir -p "$BASHCGI_DIR"
                            FORMFILES="$FORMFILES${FORMFILES:+ }$var"
                            declare -x "FORMFILE_$var=$BASHCGI_DIR/${var}"
                            mv $BASHCGI_TMP "$BASHCGI_DIR/${var}"
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
        local var="${BASH_REMATCH[1]}"
        local val="${BASH_REMATCH[2]}"
        s="${BASH_REMATCH[3]}"
        [[ $val =~ [%+] ]] && val=$(urldecode "$val")
        aa["$var"]="$val"
        trace "Found key '$var', value '$val'"
    done
    trace "aa: $aa"
    trace "Keys: ${!aa[@]}"
    trace "Values: ${aa[@]}"
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

parse_request
parse_cookies

trace "FORMS: ${!FORMS[@]}, ${FORMS[@]}"
