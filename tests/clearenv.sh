# source this file after a test to reset the env vars.

# remove temp files, before erasing the BASHCGI_DIR var
[ -n "$BASHCGI_DIR" ] && [ -d "$BASHCGI_DIR" ] && rm -rf "$BASHCGI_DIR"
# no need for the trap anymore
trap 0

# clean env vars
unset CGIBASHOPTS_VERSION FORMS FORMFILES FORMQUERY BASHCGI_DIR FORMQUERY
unset ${!FORMFILE_*} COOKIES

# clean CGI vars
unset REQUEST_METHOD CONTENT_TYPE QUERY_STRING
