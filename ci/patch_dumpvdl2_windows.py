from pathlib import Path
import re

def load(path):
    p = Path(path)
    return p, p.read_text(encoding="utf-8")

def save(p, s):
    p.write_text(s, encoding="utf-8", newline="\n")

# dumpvdl2.c: POSIX signals + strsep/strndup
p, s = load("src/dumpvdl2.c")
helper = r'''
#ifdef _WIN32
static char *win_strsep(char **stringp, const char *delim) {
    char *start, *q;
    if(stringp == NULL || *stringp == NULL) return NULL;
    start = *stringp;
    q = start + strcspn(start, delim);
    if(*q != '\0') {
        *q = '\0';
        *stringp = q + 1;
    } else {
        *stringp = NULL;
    }
    return start;
}

static char *win_strndup(const char *src, size_t n) {
    size_t len = strlen(src);
    if(len > n) len = n;
    char *copy = malloc(len + 1);
    if(copy == NULL) return NULL;
    memcpy(copy, src, len);
    copy[len] = '\0';
    return copy;
}

#define strsep win_strsep
#define strndup win_strndup
#endif
'''
marker = '#include "gs_data.h"\n'
if helper.strip() not in s:
    if marker not in s: raise SystemExit("dumpvdl2.c include marker not found")
    s = s.replace(marker, marker + helper + "\n", 1)
pattern = re.compile(r'static void setup_signals\(\) \{\n.*?\n\}\n\nstatic void pthread_barrier_new', re.S)
replacement = r'''static void setup_signals() {
#ifdef _WIN32
    signal(SIGINT, sighandler);
    signal(SIGTERM, sighandler);
#else
    struct sigaction sigact, pipeact;
    memset(&sigact, 0, sizeof(sigact));
    memset(&pipeact, 0, sizeof(pipeact));
    pipeact.sa_handler = SIG_IGN;
    sigact.sa_handler = &sighandler;
    sigaction(SIGPIPE, &pipeact, NULL);
    sigaction(SIGHUP, &sigact, NULL);
    sigaction(SIGINT, &sigact, NULL);
    sigaction(SIGQUIT, &sigact, NULL);
    sigaction(SIGTERM, &sigact, NULL);
#endif
}

static void pthread_barrier_new'''
s, n = pattern.subn(replacement, s, count=1)
if n != 1: raise SystemExit(f"setup_signals replacement count={n}")
save(p, s)

# kvargs.c: second upstream use of POSIX strsep.
p, s = load("src/kvargs.c")
marker_kv = '#include "kvargs.h"\n'
compat_kv = r'''
#ifdef _WIN32
static char *win_kv_strsep(char **stringp, const char *delim) {
    char *start, *q;
    if(stringp == NULL || *stringp == NULL) return NULL;
    start = *stringp;
    q = start + strcspn(start, delim);
    if(*q != '\0') {
        *q = '\0';
        *stringp = q + 1;
    } else {
        *stringp = NULL;
    }
    return start;
}
#define strsep win_kv_strsep
#endif
'''
if marker_kv not in s: raise SystemExit("kvargs include marker not found")
s = s.replace(marker_kv, marker_kv + compat_kv + "\n", 1)
save(p, s)

# fmtr-text.c: Windows time_t is 64-bit while timeval.tv_sec is long in MinGW.
p, s = load("src/fmtr-text.c")
old = '''static la_vstring *format_timestamp(struct timeval tv) {
\tstruct tm *tmstruct = (Config.utc == true ? gmtime(&tv.tv_sec) : localtime(&tv.tv_sec));
'''
new = '''static la_vstring *format_timestamp(struct timeval tv) {
\ttime_t ts = (time_t)tv.tv_sec;
\tstruct tm *tmstruct = (Config.utc == true ? gmtime(&ts) : localtime(&ts));
'''
if old not in s: raise SystemExit("fmtr-text timestamp marker not found")
s = s.replace(old, new, 1)
old_tz = '''\tstrftime(tbuf, sizeof(tbuf), "%F %T", tmstruct);
\tstrftime(tzbuf, sizeof(tzbuf), "%Z", tmstruct);
'''
new_tz = '''\tstrftime(tbuf, sizeof(tbuf), "%F %T", tmstruct);
\tif(Config.utc == true) {
\t\t/* MinGW strftime("%Z") may return an empty string for UTC. */
\t\tsnprintf(tzbuf, sizeof(tzbuf), "GMT");
\t} else {
\t\tstrftime(tzbuf, sizeof(tzbuf), "%Z", tmstruct);
\t}
'''
if old_tz not in s: raise SystemExit("fmtr-text timezone marker not found")
s = s.replace(old_tz, new_tz, 1)
save(p, s)

# avlc.h: keep the 24-bit address, 3-bit type and 1-bit status in one
# uint32_t bitfield allocation unit. Mixed uint32_t/uint8_t bitfields are
# laid out differently by MinGW/MS ABI and caused valid addresses to be
# labelled "reserved" and Command/Response to be decoded incorrectly.
p, s = load("src/avlc.h")
if s.count("uint8_t status:1;") != 2 or s.count("uint8_t type:3;") != 2:
    raise SystemExit("avlc.h bitfield layout markers not found")
s = s.replace("uint8_t status:1;", "uint32_t status:1;")
s = s.replace("uint8_t type:3;", "uint32_t type:3;")
save(p, s)

# Use Winsock byte-order helpers on Windows.
for path in ("src/idrp.c", "src/input-raw_frames_file.c"):
    p, s = load(path)
    old = "#include <arpa/inet.h>"
    new = '''#ifdef _WIN32
#include <winsock2.h>
#else
#include <arpa/inet.h>
#endif'''
    if old not in s: raise SystemExit(f"{path}: arpa include not found")
    s = s.replace(old, new, 1)
    save(p, s)

# output-file.c: byte order + POSIX re-entrant time helpers.
p, s = load("src/output-file.c")
old = "#include <arpa/inet.h>                  // htons"
new = '''#ifdef _WIN32
#include <winsock2.h>                   // htons
#else
#include <arpa/inet.h>                  // htons
#endif'''
if old not in s: raise SystemExit("output-file arpa include not found")
s = s.replace(old, new, 1)
marker = '#include "dumpvdl2.h"                   // do_exit, option_descr_t\n'
compat = r'''
#ifdef _WIN32
static struct tm *dumpvdl2_gmtime_r(const time_t *t, struct tm *out) {
    struct tm *tmp = gmtime(t);
    if(tmp == NULL) return NULL;
    *out = *tmp;
    return out;
}
static struct tm *dumpvdl2_localtime_r(const time_t *t, struct tm *out) {
    struct tm *tmp = localtime(t);
    if(tmp == NULL) return NULL;
    *out = *tmp;
    return out;
}
#define gmtime_r dumpvdl2_gmtime_r
#define localtime_r dumpvdl2_localtime_r
#endif
'''
if marker not in s: raise SystemExit("output-file dumpvdl2 include marker not found")
s = s.replace(marker, marker + compat + "\n", 1)

# Date-stamp Windows log files by default when no explicit rotation mode is
# supplied. stdout ("-") is still forced to ROT_NONE by out_file_init().
old = '''\t} else {
\t\tcfg->rotate = ROT_NONE;
\t}
\treturn cfg;
'''
new = '''\t} else {
#ifdef _WIN32
\t\tcfg->rotate = ROT_DAILY;
#else
\t\tcfg->rotate = ROT_NONE;
#endif
\t}
\treturn cfg;
'''
if old not in s: raise SystemExit("output-file default rotation marker not found")
s = s.replace(old, new, 1)
save(p, s)

# output-udp.c: native Winsock2 implementation while keeping POSIX path unchanged.
p, s = load("src/output-udp.c")
old = '''#include <unistd.h>                     // close
#include <errno.h>                      // errno
#include <sys/types.h>                  // socket, connect
#include <sys/socket.h>                 // socket, connect
#include <netdb.h>                      // getaddrinfo
'''
new = '''#include <errno.h>                      // errno
#ifdef _WIN32
#include <winsock2.h>
#include <ws2tcpip.h>
typedef SOCKET dump_socket_t;
#define DUMP_INVALID_SOCKET INVALID_SOCKET
#define DUMP_SOCKET_ERROR SOCKET_ERROR
#define dump_socket_close closesocket
static int dump_socket_write(dump_socket_t s, const void *buf, size_t len) {
    return send(s, (const char *)buf, (int)len, 0);
}
#else
#include <unistd.h>                     // close, write
#include <sys/types.h>                  // socket, connect
#include <sys/socket.h>                 // socket, connect
#include <netdb.h>                      // getaddrinfo
typedef int dump_socket_t;
#define DUMP_INVALID_SOCKET (-1)
#define DUMP_SOCKET_ERROR (-1)
#define dump_socket_close close
static ssize_t dump_socket_write(dump_socket_t s, const void *buf, size_t len) {
    return write(s, buf, len);
}
#endif
'''
if old not in s: raise SystemExit("output-udp include block not found")
s=s.replace(old,new,1)
s=s.replace('\tint sockfd;\n', '\tdump_socket_t sockfd;\n', 1)
s=s.replace('\tcfg->port = strdup(kvargs_get(kv, "port"));\n\treturn cfg;\n',
'''\tcfg->port = strdup(kvargs_get(kv, "port"));
\tcfg->sockfd = DUMP_INVALID_SOCKET;
\treturn cfg;
''',1)
init_marker='''\tout_udp_ctx_t *self = selfptr;

\tstruct addrinfo hints, *result, *rptr;
'''
init_repl='''\tout_udp_ctx_t *self = selfptr;

#ifdef _WIN32
\tWSADATA wsa_data;
\tint wsa_ret = WSAStartup(MAKEWORD(2, 2), &wsa_data);
\tif(wsa_ret != 0) {
\t\tfprintf(stderr, "output_udp: WSAStartup failed: %d\\n", wsa_ret);
\t\treturn -1;
\t}
#endif

\tstruct addrinfo hints, *result, *rptr;
'''
if init_marker not in s: raise SystemExit("output-udp init marker not found")
s=s.replace(init_marker,init_repl,1)
s=s.replace('''\tif(ret != 0) {
\t\tfprintf(stderr, "output_udp: could not resolve %s: %s\\n", self->address, gai_strerror(ret));
\t\treturn -1;
\t}
''','''\tif(ret != 0) {
#ifdef _WIN32
\t\tfprintf(stderr, "output_udp: could not resolve %s: %s\\n", self->address, gai_strerrorA(ret));
\t\tWSACleanup();
#else
\t\tfprintf(stderr, "output_udp: could not resolve %s: %s\\n", self->address, gai_strerror(ret));
#endif
\t\treturn -1;
\t}
''',1)
s=s.replace('if(self->sockfd == -1)', 'if(self->sockfd == DUMP_INVALID_SOCKET)')
s=s.replace('if(connect(self->sockfd, rptr->ai_addr, rptr->ai_addrlen) != -1)',
            'if(connect(self->sockfd, rptr->ai_addr, (int)rptr->ai_addrlen) != DUMP_SOCKET_ERROR)')
s=s.replace('close(self->sockfd);', 'dump_socket_close(self->sockfd);')
s=s.replace('self->sockfd = 0;', 'self->sockfd = DUMP_INVALID_SOCKET;')
s=s.replace('ASSERT(self->sockfd != 0);', 'ASSERT(self->sockfd != DUMP_INVALID_SOCKET);')
s=s.replace('write(self->sockfd, msg->buf, msg->len)', 'dump_socket_write(self->sockfd, msg->buf, msg->len)')
s=s.replace('''\tif (rptr == NULL) {
\t\tfprintf(stderr, "output_udp: Could not set up UDP socket to %s:%s: all addresses failed\\n",
\t\t\t\tself->address, self->port);
\t\tself->sockfd = DUMP_INVALID_SOCKET;
\t\treturn -1;
\t}
''','''\tif (rptr == NULL) {
\t\tfprintf(stderr, "output_udp: Could not set up UDP socket to %s:%s: all addresses failed\\n",
\t\t\t\tself->address, self->port);
\t\tself->sockfd = DUMP_INVALID_SOCKET;
\t\tfreeaddrinfo(result);
#ifdef _WIN32
\t\tWSACleanup();
#endif
\t\treturn -1;
\t}
''',1)
# Add Winsock cleanup after socket close in shutdown/failure handlers.
s=s.replace('''\tdump_socket_close(self->sockfd);
}

static void out_udp_handle_failure''','''\tdump_socket_close(self->sockfd);
#ifdef _WIN32
\tWSACleanup();
#endif
}

static void out_udp_handle_failure''',1)
s=s.replace('''\tdump_socket_close(self->sockfd);
}

static const option_descr_t''','''\tdump_socket_close(self->sockfd);
#ifdef _WIN32
\tWSACleanup();
#endif
}

static const option_descr_t''',1)
save(p, s)

# Link Winsock for MinGW builds.
p, s = load("src/CMakeLists.txt")
marker = 'find_library(LIBM m REQUIRED)\n'
addition = '''find_library(LIBM m REQUIRED)

if(MINGW)
\tlist(APPEND dumpvdl2_extra_libs ws2_32)
endif()
'''
if marker not in s: raise SystemExit("CMake LIBM marker not found")
s=s.replace(marker,addition,1)
save(p,s)

print("Applied dumpvdl2 Windows compatibility rewrites")
