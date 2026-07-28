import re
from django_hosts import patterns, host

host_patterns = patterns(
    "",
    host(re.sub(r"_", r"-", r"arches_bng"), "arches_bng.urls", name="arches_bng"),
)
