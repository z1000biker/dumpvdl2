/*
 *  This file is a part of dumpvdl2
 *
 *  Copyright (c) 2017-2026 Tomasz Lemiech <szpajder@gmail.com>
 *
 *  This program is free software: you can redistribute it and/or modify
 *  it under the terms of the GNU General Public License as published by
 *  the Free Software Foundation, either version 3 of the License, or
 *  (at your option) any later version.
 *
 *  This program is distributed in the hope that it will be useful,
 *  but WITHOUT ANY WARRANTY; without even the implied warranty of
 *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *  GNU General Public License for more details.
 *
 *  You should have received a copy of the GNU General Public License
 *  along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

#include <stdio.h>                      // fprintf
#include <string.h>                     // strdup, strerror
#include <errno.h>                      // errno
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
#include "output-common.h"              // output_descriptor_t, output_qentry_t, output_queue_drain
#include "kvargs.h"                     // kvargs, option_descr_t
#include "dumpvdl2.h"                   // do_exit

typedef struct {
	char *address;
	char *port;
	dump_socket_t sockfd;
} out_udp_ctx_t;

static bool out_udp_supports_format(output_format_t format) {
	return(format == OFMT_TEXT || format == OFMT_JSON || format == OFMT_PP_ACARS);
}

static void *out_udp_configure(kvargs *kv) {
	ASSERT(kv != NULL);
	NEW(out_udp_ctx_t, cfg);
	if(kvargs_get(kv, "address") == NULL) {
		fprintf(stderr, "output_udp: IP address not specified\n");
		goto fail;
	}
	cfg->address = strdup(kvargs_get(kv, "address"));
	if(kvargs_get(kv, "port") == NULL) {
		fprintf(stderr, "output_udp: UDP port not specified\n");
		goto fail;
	}
	cfg->port = strdup(kvargs_get(kv, "port"));
	cfg->sockfd = DUMP_INVALID_SOCKET;
	return cfg;
fail:
	XFREE(cfg);
	return NULL;
}

static int out_udp_init(void *selfptr) {
	ASSERT(selfptr != NULL);
	out_udp_ctx_t *self = selfptr;

#ifdef _WIN32
	WSADATA wsa_data;
	int wsa_ret = WSAStartup(MAKEWORD(2, 2), &wsa_data);
	if(wsa_ret != 0) {
		fprintf(stderr, "output_udp: WSAStartup failed: %d\n", wsa_ret);
		return -1;
	}
#endif

	struct addrinfo hints, *result, *rptr;
	memset(&hints, 0, sizeof(struct addrinfo));
	hints.ai_family = AF_UNSPEC;
	hints.ai_socktype = SOCK_DGRAM;
	hints.ai_flags = 0;
	hints.ai_protocol = 0;
	int ret = getaddrinfo(self->address, self->port, &hints, &result);
	if(ret != 0) {
#ifdef _WIN32
		fprintf(stderr, "output_udp: could not resolve %s: %s\n", self->address, gai_strerrorA(ret));
		WSACleanup();
#else
		fprintf(stderr, "output_udp: could not resolve %s: %s\n", self->address, gai_strerror(ret));
#endif
		return -1;
	}
	for (rptr = result; rptr != NULL; rptr = rptr->ai_next) {
		self->sockfd = socket(rptr->ai_family, rptr->ai_socktype, rptr->ai_protocol);
		if(self->sockfd == DUMP_INVALID_SOCKET) {
			continue;
		}
		if(connect(self->sockfd, rptr->ai_addr, (int)rptr->ai_addrlen) != DUMP_SOCKET_ERROR) {
			break;
		}
		dump_socket_close(self->sockfd);
		self->sockfd = DUMP_INVALID_SOCKET;
	}
	if (rptr == NULL) {
		fprintf(stderr, "output_udp: Could not set up UDP socket to %s:%s: all addresses failed\n",
				self->address, self->port);
		self->sockfd = DUMP_INVALID_SOCKET;
		freeaddrinfo(result);
#ifdef _WIN32
		WSACleanup();
#endif
		return -1;
	}
	freeaddrinfo(result);
	return 0;
}

static void out_udp_produce_pp_acars(out_udp_ctx_t *self, vdl2_msg_metadata *metadata, octet_string_t *msg) {
	UNUSED(metadata);
	ASSERT(msg != NULL);
	ASSERT(self->sockfd != DUMP_INVALID_SOCKET);
	if(msg->len < 1) {
		return;
	}
	if(dump_socket_write(self->sockfd, msg->buf, msg->len) < 0) {
		debug_print(D_OUTPUT, "output_udp: error while writing to the network socket: %s", strerror(errno));
	}
}

static void out_udp_produce_text(out_udp_ctx_t *self, vdl2_msg_metadata *metadata, octet_string_t *msg) {
	UNUSED(metadata);
	ASSERT(msg != NULL);
	ASSERT(self->sockfd != DUMP_INVALID_SOCKET);
	if(msg->len < 2) {
		return;
	}
	if(dump_socket_write(self->sockfd, msg->buf, msg->len) < 0) {
		debug_print(D_OUTPUT, "output_udp: error while writing to the network socket: %s", strerror(errno));
	}
}

static int out_udp_produce(void *selfptr, output_format_t format, vdl2_msg_metadata *metadata, octet_string_t *msg) {
	ASSERT(selfptr != NULL);
	out_udp_ctx_t *self = selfptr;
	if(format == OFMT_TEXT || format == OFMT_JSON) {
		out_udp_produce_text(self, metadata, msg);
	} else if(format == OFMT_PP_ACARS) {
		out_udp_produce_pp_acars(self, metadata, msg);
	}
	return 0;
}

static void out_udp_handle_shutdown(void *selfptr) {
	ASSERT(selfptr != NULL);
	out_udp_ctx_t *self = selfptr;
	fprintf(stderr, "output_udp(%s:%s): shutting down\n", self->address, self->port);
	dump_socket_close(self->sockfd);
#ifdef _WIN32
	WSACleanup();
#endif
}

static void out_udp_handle_failure(void *selfptr) {
	ASSERT(selfptr != NULL);
	out_udp_ctx_t *self = selfptr;
	fprintf(stderr, "output_udp: can't connect to %s:%s, deactivating output\n",
			self->address, self->port);
	dump_socket_close(self->sockfd);
#ifdef _WIN32
	WSACleanup();
#endif
}

static const option_descr_t out_udp_options[] = {
	{
		.name = "address",
		.description = "Destination host name or IP address (required)"
	},
	{
		.name = "port",
		.description = "Destination UDP port (required)"
	},
	{
		.name = NULL,
		.description = NULL
	}
};

output_descriptor_t out_DEF_udp = {
	.name = "udp",
	.description = "Output to a remote host via UDP",
	.options = out_udp_options,
	.supports_format = out_udp_supports_format,
	.configure = out_udp_configure,
	.init = out_udp_init,
	.produce = out_udp_produce,
	.handle_shutdown = out_udp_handle_shutdown,
	.handle_failure = out_udp_handle_failure
};
