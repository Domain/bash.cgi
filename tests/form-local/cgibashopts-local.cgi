#!/bin/bash
set -u
set -e
. cgibashopts

title="CGI BASH opts upload test on a local host"
header="Content-Type: text/html$nl$nl<html><head><title>$title</title>
</head><body><h1>$title</h1>"
footer=""

################################# Options
export data=/tmp/cgibashopts-formfiletest.data
err() { echo "***ERROR: $*" >&2; exit -1; }

################################# Code
main() {
    echo "$header"
    if [ -n "${FORM_file:-}" ]; then
	src="/tmp/${FORM_file##*/}"
	[ "$FORMFILES" = file ] || echo "<p>***Error, FORMFILES=$FORMFILES</p>"
        if [ -d "$BASHCGI_DIR" ]; then
	    if [ -e "$BASHCGI_DIR/file" ]; then
	        if [ -s "$BASHCGI_DIR/file" ]; then
		    if [ -s "$src" ]; then
		        if cmp -s "$src" "$BASHCGI_DIR/file"; then
			    echo "<p>Upload of \"$src\" successful</p>"
		        else
			    echo "<p>***Error, file uploaded differ</p>"
		        fi
		    else
		        echo "<p>***Error, src file \"$src\" empty</p>"
		    fi
	        else
		    echo "<p>***Error, file uploaded empty</p>"
	        fi
	    else
	        echo "<p>***Error no uploaded file!</p>"
	    fi
        else
            echo "<p>***Error no directory \"BASHCGI_DIR\"</p>"
        fi
    fi
    echo "<b>Contents of \"BASHCGI_DIR\":</b><pre>"
    (cd "$BASHCGI_DIR" && ls -l)
    echo "</pre><hr>"
    form_page
}

form_page() {
    echo "<form method=POST enctype='multipart/form-data'>
<br>File: <input type=file name=file size=32>
<br><input type=submit value=Upload> 
</form>
<p><b>Note:</b> for comparing with the source, the uploaded files must also be found in the server /tmp/ directory, which may not be the real /tmp/ directory"    
    echo "$footer"
}

main
