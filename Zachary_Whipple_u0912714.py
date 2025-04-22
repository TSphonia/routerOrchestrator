import argparse
import subprocess

def print_help():
    print("""
Commands:
  create-topology       Create the network topology
  start-ospf            Start and configure OSPF daemons
  install-host-routes   Set static routes on hosts
  switch-path north     Change OSPF weights to switch traffic path to the north
  switch-path south     Change OSPF weights to switch traffic path to the south
  exit|quit             Close the program, destructing all docker containers

  Ensure that create-topology is run before any other commands except exit.
  Ensure start-ospf has been run before using switch-path.
""")

def main():
    parser = argparse.ArgumentParser(description="POWDER Orchestrator", add_help=False)
    parser.add_argument("-h", action="store_true")
    args = parser.parse_args()


    if args.h:
        print_help()
        return

    while True:
        cmd = input(">>> ").strip()
        if cmd == "create-topology":
            create_topology()
            topology_created = True
        elif cmd == "start-ospf":
            start_ospf()
            ospf_started = True
        elif cmd == "install-host-routes":
            install_routes()
        elif cmd.startswith("switch-path"):
            _, path = cmd.split()
            switch_path(path)
        elif cmd in {"exit", "quit"}:
            destroy_topology()
            break
        else:
            print("Unknown command")

def create_topology():
    print("Creating topology using docker-compose...")
    subprocess.run(["sudo", "bash", "-c", "docker compose up -d"], check=True)

def destroy_topology():
    print("Tearing down topology...")
    subprocess.run(["sudo", "bash", "-c", "docker compose down"], check=True)

def run(cmd):
    print(f"[RUN] {cmd}")
    subprocess.run(["sudo", "bash", "-c", cmd], check=True)

def install_frr(container):
    print(f"Installing FRR on {container}...")

    run(f"docker exec -i {container} bash -c 'apt -y install curl'")
    run(f"docker exec -i {container} bash -c 'apt -y install gnupg'")
    run(f"docker exec -i {container} bash -c 'curl -s https://deb.frrouting.org/frr/keys.gpg | tee /usr/share/keyrings/frrouting.gpg > /dev/null'")
    run(f"docker exec -i {container} bash -c 'apt install -y lsb-release'")
    run(f"docker exec -i {container} bash -c 'FRRVER=frr-stable && "
        "echo deb [signed-by=/usr/share/keyrings/frrouting.gpg] https://deb.frrouting.org/frr $(lsb_release -s -c) $FRRVER "
        "| tee -a /etc/apt/sources.list.d/frr.list'")

    run(f"docker exec -i {container} bash -c 'apt update && apt -y install frr frr-pythontools'")
    run(f"docker exec -i {container} bash -c \"sed -i 's/^ospfd=no/ospfd=yes/' /etc/frr/daemons && service frr restart\"")

    print(f"Verifying ospfd is running on {container}...")
    run(f"docker exec -i {container} bash -c 'ps -ef | grep ospf'")

def configure_ospf_r1(container):
    print(f"Configuring OSPF on {container}...")

    config_commands = """
    configure terminal
    router ospf
     ospf router-id 1.1.1.1
     network 10.0.10.0/24 area 0.0.0.0
     network 10.0.11.0/24 area 0.0.0.0
     network 10.0.12.0/24 area 0.0.0.0
    exit
    interface eth0
     ip ospf cost 5
    exit
    interface eth1
     ip ospf cost 5
    exit
    interface eth2
     ip ospf cost 5
    exit
    write memory
    """
    run(f"echo '{config_commands.strip()}' | sudo docker exec -i {container} vtysh")

def configure_ospf_r2(container):
    print(f"Configuring OSPF on {container}...")

    config_commands = """
    configure terminal
    router ospf
     ospf router-id 2.2.2.2
     network 10.0.11.0/24 area 0.0.0.0
     network 10.0.13.0/24 area 0.0.0.0
    exit
    interface eth0
     ip ospf cost 5
    exit
    interface eth1
     ip ospf cost 5
    exit
    write memory
    """
    run(f"echo '{config_commands.strip()}' | sudo docker exec -i {container} vtysh")

def configure_ospf_r3(container):
    print(f"Configuring OSPF on {container}...")

    config_commands = """
    configure terminal
    router ospf
     ospf router-id 3.3.3.3
     network 10.0.13.0/24 area 0.0.0.0
     network 10.0.14.0/24 area 0.0.0.0
     network 10.0.15.0/24 area 0.0.0.0
    exit
    interface eth0
     ip ospf cost 5
    exit
    interface eth1
     ip ospf cost 5
    exit
    interface eth2
     ip ospf cost 5
    exit
    write memory
    """
    run(f"echo '{config_commands.strip()}' | sudo docker exec -i {container} vtysh")

def configure_ospf_r4(container):
    print(f"Configuring OSPF on {container}...")

    config_commands = """
    configure terminal
    router ospf
     ospf router-id 4.4.4.4
     network 10.0.12.0/24 area 0.0.0.0
     network 10.0.14.0/24 area 0.0.0.0
    exit
    interface eth0
     ip ospf cost 50
    exit
    interface eth1
     ip ospf cost 50
    exit
    write memory
    """
    run(f"echo '{config_commands.strip()}' | sudo docker exec -i {container} vtysh")

def start_ospf():
    install_frr("part1-r1-1")
    configure_ospf_r1("part1-r1-1")

    install_frr("part1-r2-1")
    configure_ospf_r2("part1-r2-1")

    install_frr("part1-r3-1")
    configure_ospf_r3("part1-r3-1")

    install_frr("part1-r4-1")
    configure_ospf_r4("part1-r4-1")

def install_routes():
    print("Installing static routes on hosts...")

    # Host A (part1-ha-1) needs to reach Host B's network (10.0.15.0/24) through Router 1
    run("docker exec -it part1-ha-1 route add -net 10.0.15.0/24 gw 10.0.10.4")

    # Host B (part1-hb-1) needs to reach Host A's network (10.0.10.0/24) through Router 3
    run("docker exec -it part1-hb-1 route add -net 10.0.10.0/24 gw 10.0.15.4")

    print("Static routes installed.")

def switch_path(direction):
    if direction not in ("north", "south"):
        print("Invalid direction. Use 'north' or 'south'.")
        return

    print(f"Switching OSPF path to the {direction} route...")

    if direction == "north":
        r2_cost = 5
        r4_cost = 50
    else:
        r2_cost = 50
        r4_cost = 5

    # Change R2 costs
    r2_cmds = [
        "configure terminal",
        "interface eth0",
        f"ip ospf cost {r2_cost}",
        "exit",
        "interface eth1",
        f"ip ospf cost {r2_cost}",
        "exit",
        "write memory"
    ]
    run(f"docker exec -i part1-r2-1 vtysh " + " ".join(f"-c '{cmd}'" for cmd in r2_cmds))

    # Change R4 costs
    r4_cmds = [
        "configure terminal",
        "interface eth0",
        f"ip ospf cost {r4_cost}",
        "exit",
        "interface eth1",
        f"ip ospf cost {r4_cost}",
        "exit",
        "write memory"
    ]
    run(f"docker exec -i part1-r4-1 vtysh " + " ".join(f"-c '{cmd}'" for cmd in r4_cmds))

    print(f"Path successfully switched to {direction} path.")

if __name__ == "__main__":
    main()
