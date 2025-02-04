import os
import shlex
from clustersConfig import ClustersConfig
from clustersConfig import NodeConfig
from bmc import BmcConfig
import dhcpConfig
import common
import host


def _pxeboot_marvell_dpu(name: str, bmc: BmcConfig, mac: str, ip: str, iso: str) -> None:
    # For Marvell DPU, we require that our "BMC" is the host on has the DPU
    # plugged in.
    #
    # We also assume, that the user name is "core" and that we can SSH into
    # that host with public key authentication. We ignore the `bmc.user`
    # setting. The reason for that is so that dpu-operator's
    # "hack/cluster-config/config-dpu.yaml" (which should work with IPU and
    # Marvell DPU) does not need to specify different BMC user name and
    # passwords. If you solve how to express the BMC authentication in the
    # cluster config in a way that is suitable for IPU and Marvell DPU at the
    # same time (e.g. via Jinja2 templates), we can start honoring
    # bmc.user/bmc.password.
    rsh = host.RemoteHost(bmc.url)
    rsh.ssh_connect("core")

    ip_addr = f"{ip}/24"
    ip_gateway, _ = dhcpConfig.get_subnet_range(ip, "255.255.255.0")

    # An empty entry means to use the host's "id_ed25519.pub". We want that.
    ssh_keys = [""]
    for _, pub_key_content, _ in common.iterate_ssh_keys():
        ssh_keys.append(pub_key_content)

    ssh_key_options = [f"--ssh-key={shlex.quote(s)}" for s in ssh_keys]

    image = os.environ.get("CDA_MARVELL_TOOLS_IMAGE", "quay.io/sdaniele/marvell-tools:latest")

    r = rsh.run(
        "sudo "
        "podman "
        "run "
        "--pull always "
        "--rm "
        "--replace "
        "--privileged "
        "--pid host "
        "--network host "
        "--user 0 "
        "--name marvell-tools "
        "-i "
        "-v /:/host "
        "-v /dev:/dev "
        f"{shlex.quote(image)} "
        "./pxeboot.py "
        f"--dpu-name={shlex.quote(name)} "
        "--host-mode=coreos "
        f"--nm-secondary-cloned-mac-address={shlex.quote(mac)} "
        f"--nm-secondary-ip-address={shlex.quote(ip_addr)} "
        f"--nm-secondary-ip-gateway={shlex.quote(ip_gateway)} "
        "--yum-repos=rhel-nightly "
        "--default-extra-packages "
        f"{' '.join(ssh_key_options)} "
        f"{shlex.quote(iso)} "
        "2>&1"
    )
    if not r.success():
        raise RuntimeError(f"Failure to to pxeboot: {r}")


def MarvellIsoBoot(cc: ClustersConfig, node: NodeConfig, iso: str) -> None:
    assert node.ip is not None
    assert node.bmc is not None
    _pxeboot_marvell_dpu(node.name, node.bmc, node.mac, node.ip, iso)
    dhcpConfig.configure_iso_network_port(cc.network_api_port, node.ip)
    dhcpConfig.configure_dhcpd(node)


def main() -> None:
    pass


if __name__ == "__main__":
    main()
