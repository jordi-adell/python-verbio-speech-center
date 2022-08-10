variables {
  DOCKER_REGISTRY = "docker.registry.verbio.com/csr"
  STAGE = "testing"
  VERSION = "latest"
}


job "asr4" {
  datacenters = ["dc1"]
  type        = "service"

  meta {
    ASR4_VERSION = "${var.VERSION}"
  }

  group "asr4-group" {
    count = 1

    restart {
      attempts = 10
      interval = "5m"
      delay    = "25s"
      mode     = "delay"
    }

    network {
      port "grpc-port" {
        static = 50051
        to = 50051
      }
    }

    task "asr4-service" {
      driver = "docker"

      config {
        image              = "${var.DOCKER_REGISTRY}/${var.STAGE}/asr4:${var.VERSION}"
        ports              = ["grpc-port"]
      }

      logs {
        max_files     = 10
        max_file_size = 10
      }

      resources {
        memory = 250
      }

      service {
        name = "asr4-service"
        port = "grpc-port"

        check {
          name = "up-and-running"
          type = "grpc"
          interval = "30s"
          timeout = "2s"
        }
      }
    }
  }
}