#!/usr/bin/env python3

import sys
import re
from itertools import zip_longest 
import portage
import portage.versions

from packagekit.backend import PackageKitBaseBackend, get_package_id
from packagekit.enums import STATUS_QUERY, INFO_INSTALLED, INFO_AVAILABLE
from packagekit.progress import PackagekitProgress

import inspect
print(inspect.signature(PackageKitBaseBackend.package))

def compute_equal_steps(iterable):
    if not iterable:
        return []
    return [idx * (100.0 / len(iterable))
            for idx, _ in enumerate(iterable, start=1)]

class PortageBackend(PackageKitBaseBackend):
    open("/tmp/custom_helper_called", "a").write(f"called with {inspect.signature(PackageKitBaseBackend.package)}\n")
    def __init__(self, args):
        super().__init__(args)

    def _get_all_cp(self, filters):
        return portage.db[portage.root]["porttree"].dbapi.cp_all()

    def _get_all_cpv(self, cp, filters):
        return portage.db[portage.root]["porttree"].dbapi.match(cp)

    def _package(self, cpv, info=None):
        cp = portage.cpv_getkey(cpv)
        cat, pn = portage.catsplit(cp)
        ver = portage.versions.cpv_getversion(cpv)

        try:
            keywords = portage.db[portage.root]["porttree"].dbapi.aux_get(cpv, ["KEYWORDS"])[0].split()
            arch = keywords[0] if keywords else portage.settings.get("ARCH", "amd64")
        except Exception:
            arch = portage.settings.get("ARCH", "amd64")

        repo = "gentoo"
        pkgid = get_package_id(pn, ver, arch, repo)

        try:
            desc = portage.db[portage.root]["porttree"].dbapi.aux_get(cpv, ["DESCRIPTION"])[0]
        except Exception:
            desc = ""

        if info is None:
            info = INFO_AVAILABLE

        # Correct Python 3 signature
        self.package(pkgid, info, desc)

    def search_name(self, filters, keys_list):
        self.status(STATUS_QUERY)
        self.allow_cancel(True)

        categories = []
        for k in keys_list[:]:
            if "/" in k:
                cat, cp = portage.versions.catsplit(k)
                categories.append(cat)
                keys_list[keys_list.index(k)] = cp

        category_filter = None
        if len(categories) > 1:
            return
        elif len(categories) == 1:
            category_filter = categories[0]

        search_list = []
        for k in keys_list:
            k = re.escape(k)
            search_list.append(re.compile(k, re.IGNORECASE))

        cp_list = self._get_all_cp(filters)

        progress = compute_equal_steps(cp_list)
        self.percentage(0)

        for percentage, cp in zip(progress, cp_list):
            if category_filter:
                cat, pkg_name = portage.versions.catsplit(cp)
                if cat != category_filter:
                    continue
            else:
                pkg_name = portage.versions.catsplit(cp)[1]

            found = True
            for s in search_list:
                if not s.search(pkg_name):
                    found = False
                    break
            if found:
                for cpv in self._get_all_cpv(cp, filters):
                    self._package(cpv)

            self.percentage(percentage)

        self.percentage(100)

def main():
    backend = PortageBackend(sys.argv[1:])
    backend.dispatcher(sys.argv[1:])
    return 0

if __name__ == "__main__":
    sys.exit(main())
