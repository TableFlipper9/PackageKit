#!/usr/bin/env python3
import sys
from packagekit.backend import PackageKitBaseBackend

class HelloBackend(PackageKitBaseBackend):
    def __init__(self, args):
        super().__init__(args)

    def search_name(self, filters, values):
        pkgid = "hello;1.0;x86_64;portage"
        summary = "Hello from custom backend (search_name)!"
        self.package("available", pkgid, summary)

    def search_details(self, filters, values):
        pkgid = "hello;1.0;x86_64;portage"
        summary = "Hello from custom backend!"
        license = "GPL"
        group = "System"
        description = "This is a fake package from the custom backend"
        url = "http://example.com"

        self.status("Custom backend search started")
        self.package("available", pkgid, summary)
        self.details(pkgid, summary, license, group, description, url, 0)

def main():
    backend = HelloBackend(sys.argv[1:])
    backend.dispatcher(sys.argv[1:])
    return 0

if __name__ == "__main__":
    sys.exit(main())
