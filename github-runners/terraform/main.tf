locals {
    charm_name = "github-runner"
    charm_channel = "latest/stable"
    charm_base = "ubuntu@22.04"
    dockerhub_mirror        = "https://github-runner-dockerhub-cache.canonical.com:5000"
    experimental-use-aproxy = true
    runner-storage          = "juju-storage"
    reconcile-interval      = 10
    
    denylist_testflinger    = <<-EOT
    0.0.0.0/8,
    10.0.0.0/8,
    100.64.0.0/10,
    127.0.0.0/8,
    169.254.0.0/16,
    172.16.0.0/12,
    192.0.0.0/24,
    192.0.2.0/24,
    192.88.99.0/24,
    192.168.0.0/16,
    198.18.0.0/15,
    198.51.100.0/24,
    203.0.113.0/24,
    224.0.0.0/4,
    233.252.0.0/24,
    240.0.0.0/4
    EOT
}

provider "juju" {}

resource "juju_application" "github-runner-testflinger" {
    name  = "github-runner-testflinger"
    model = "stg-self-hosted-runners-testflinger-action-testing"
    constraints = "arch=amd64 cores=8 mem=16384M root-disk=20480M"

    charm {
        name = local.charm_name
        channel = local.charm_channel
        base = local.charm_base
    }

    config = {
        path = "canonical/hwcert-jenkins-tools"
        labels = "testflinger"
        token = var.github_personal_access_token
        virtual-machines = 1
        vm-cpu = 4
        vm-memory = "8GiB"
        vm-disk = "18GiB"
        # denylist = local.denylist_testflinger
        dockerhub-mirror = local.dockerhub_mirror
        runner-storage = "juju-storage"
    }

    units = 2
}
