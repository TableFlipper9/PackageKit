#!/usr/bin/env python3
import sys
import re
import signal
import traceback
from collections import defaultdict

from itertools import zip_longest

from packagekit.backend import (
    PackageKitBaseBackend,
    get_package_id,
    split_package_id,
)
from packagekit.enums import *
from packagekit.progress import PackagekitProgress

import portage
import portage.dep
import portage.versions
from portage.exception import InvalidAtom

def compute_equal_steps(iterable):
    if not iterable:
        return []
    return [idx * (100.0 / len(iterable))
            for idx, _ in enumerate(iterable, start=1)]

class PortageBackend(PackageKitBaseBackend):
    def __init__(self, args):
        super().__init__(args)

    def _get_all_cp(self, filters):
        cp_list = []

        if FILTER_INSTALLED in filters:
            cp_list = self.pvar.vardb.cp_all()
        elif FILTER_NOT_INSTALLED in filters:
            cp_list = self.pvar.portdb.cp_all()
        else:
            # need installed packages first
            cp_list = self.pvar.vardb.cp_all()
            for cp in self.pvar.portdb.cp_all():
                if cp not in cp_list:
                    cp_list.append(cp)

        return cp_list

    def _get_all_cpv(self, cp, filters):
        return portage.db[portage.root]["porttree"].dbapi.match(cp)

    def _get_metadata(self, cpv, fields):
        try:
            return portage.db[portage.root]["porttree"].dbapi.aux_get(cpv, fields)
        except Exception:
            return ["" for _ in fields]

    def _is_installed(self, cpv):
        return bool(portage.db[portage.root]["vartree"].dbapi.match(cpv))

    def _cpv_to_id(self, cpv):
        cp = portage.cpv_getkey(cpv)
        cat, pn = portage.catsplit(cp)
        ver = portage.versions.cpv_getversion(cpv)
        repo = "gentoo"  # hardcoded for now
        arch = portage.settings.get("ARCH", "amd64")
        return get_package_id(pn, ver, arch, repo)

    def _package(self, cpv, info=None):
        desc = self._get_metadata(cpv, ["DESCRIPTION"])[0]
        if not info:
            if self._is_installed(cpv):
                info = INFO_INSTALLED
            else:
                info = INFO_AVAILABLE
        self.package(self._cpv_to_id(cpv), info, desc)

    def search_details(self, filters, keys):
        self.status(STATUS_QUERY)
        self.allow_cancel(True)

        cp_list = self._get_all_cp(filters)
        search_list = self._get_search_list(keys)

        progress = PackagekitProgress(compute_equal_steps(cp_list))
        self.percentage(progress.percent)

        for percentage, cp in zip(progress, cp_list):
            cpv_list = []

            for cpv in self._get_all_cpv(cp, filters, filter_newest=False):
                match = True
                metadata = self._get_metadata(
                    cpv, ["DESCRIPTION", "HOMEPAGE", "IUSE", "LICENSE",
                          "repository", "SLOT", "EAPI", "KEYWORDS"],
                    in_dict=True
                )
                metadata["LICENSE"] = self._get_real_license_str(cpv, metadata)
                for s in search_list:
                    found = False
                    for x in metadata:
                        if s.search(metadata[x]):
                            found = True
                            break
                    if not found:
                        match = False
                        break
                if match:
                    cpv_list.append(cpv)

            cpv_list = self._filter_newest(cpv_list, filters)

            for cpv in cpv_list:
                self._package(cpv)

            self.percentage(percentage)

        self.percentage(100)

    def search_file(self, filters, values):
        self.status(STATUS_QUERY)
        self.allow_cancel(True)

        if FILTER_NOT_INSTALLED in filters:
            self.error(ERROR_CANNOT_GET_FILELIST,
                       "search-file isn't available with ~installed filter")
            return

        cpv_list = self.pvar.vardb.cpv_all()
        is_full_path = True

        progress = PackagekitProgress(compute_equal_steps(values))
        self.percentage(progress.percent)

        for percentage, key in zip(progress, values):

            if key[0] != "/":
                is_full_path = False
                key = re.escape(key)
                searchre = re.compile("/" + key + "$", re.IGNORECASE)

            cpv_list = self._filter_free(cpv_list, filters)
            nb_cpv = float(len(cpv_list))

            for cpv in cpv_list:
                for f in self._get_file_list(cpv):
                    if (is_full_path and key == f) \
                            or (not is_full_path and searchre.search(f)):
                        self._package(cpv)
                        break

            self.percentage(percentage)

        self.percentage(100)

    def search_group(self, filters, groups):
        self.status(STATUS_QUERY)
        self.allow_cancel(True)

        cp_list = self._get_all_cp(filters)

        progress = PackagekitProgress(compute_equal_steps(cp_list))
        self.percentage(progress.percent)

        for percentage, cp in zip(progress, cp_list):
            for group in groups:
                if self._get_pk_group(cp) == group:
                    for cpv in self._get_all_cpv(cp, filters):
                        self._package(cpv)

            self.percentage(percentage)

        self.percentage(100)

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

        progress = PackagekitProgress(compute_equal_steps(cp_list))
        self.percentage(progress.percent)
        
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
