from conan import ConanFile
from conan.errors import ConanInvalidConfiguration
from conan.tools.files import get, apply_conandata_patches, rmdir, rm, export_conandata_patches, copy
from conan.tools.build import cross_building
from conan.tools.gnu import Autotools, AutotoolsDeps, AutotoolsToolchain, PkgConfigDeps
from conan.tools.env import Environment, VirtualRunEnv
from conan.tools.microsoft import is_msvc, unix_path
from conan.tools.apple import fix_apple_shared_install_name
import os

required_conan_version = ">=2.0.9"

class CoinCbcConan(ConanFile):
    name = "coin-cbc"
    description = "COIN-OR Branch-and-Cut solver"
    topics = ("clp", "simplex", "solver", "linear", "programming")
    url = "https://github.com/conan-io/conan-center-index"
    homepage = "https://github.com/coin-or/Clp"
    license = ("EPL-2.0",)
    settings = "os", "arch", "build_type", "compiler"
    options = {
        "shared": [True, False],
        "fPIC": [True, False],
        "parallel": [True, False],
    }
    default_options = {
        "shared": False,
        "fPIC": True,
        "parallel": False,
    }
    implements = ["auto_shared_fpic"]
    requires = {
    }
    build_requires = {
        "gnu-config/cci.20201022",
        "pkgconf/1.7.4",
        "libtool/2.4.7",
    }

    _autotools = None

    def export_sources(self):
        export_conandata_patches(self)

    def configure(self):
        if self.options.shared:
            self.options.rm_safe("fPIC")

    def requirements(self):
        self.requires("coin-utils/2.11.10", force=True)
        self.requires("coin-osi/0.108.7", force=True)
        self.requires("coin-clp/1.17.7", force=True)
        self.requires("coin-cgl/0.60.7", force=True)
        if self.settings.compiler == "msvc" and self.options.parallel:
            self.requires("pthreads4w/3.0.0")

    def build_requirements(self):
        if self.settings.compiler == "msvc":
            self.tool_requires("msys2/cci.latest")
            self.tool_requires("automake/1.16.5")

    def validate(self):
        if self.settings.os == "Windows" and self.options.shared:
            raise ConanInvalidConfiguration("coin-cbc does not support shared builds on Windows")
        # FIXME: This issue likely comes from very old autotools versions used to produce configure.
        if hasattr(self, "settings_build") and cross_building(self) and self.options.shared:
            raise ConanInvalidConfiguration("coin-cbc shared not supported yet when cross-building")

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)
        apply_conandata_patches(self)

    def generate(self):
        if not cross_building(self):
            VirtualRunEnv(self).generate(scope="build")

        tc = AutotoolsToolchain(self)
        def yes_no(v): return "yes" if v else "no"
        tc.generate()

        tc = PkgConfigDeps(self)
        tc.generate()

        deps = AutotoolsDeps(self)
        deps.generate()

        if is_msvc(self):
            env = Environment()
            automake_conf = self.dependencies.build["automake"].conf_info
            compile_wrapper = unix_path(self, automake_conf.get("user.automake:compile-wrapper", check_type=str))
            ar_wrapper = unix_path(self, automake_conf.get("user.automake:lib-wrapper", check_type=str))
            env.define("CC", f"{compile_wrapper} cl -nologo")
            env.define("CXX", f"{compile_wrapper} cl -nologo")
            env.define("LD", "link -nologo")
            env.define("AR", f"{ar_wrapper} lib")
            env.define("NM", "dumpbin -symbols")
            env.define("OBJDUMP", ":")
            env.define("RANLIB", ":")
            env.define("STRIP", ":")
            env.vars(self).save_script("conanbuild_msvc")

    def build(self):
        autotools = Autotools(self)
        # absolutely do not call autoreconf, see: https://github.com/coin-or/Cbc/issues/602
        # completely borked
        autotools.configure()
        autotools.make()

    def package(self):
        copy(self, "LICENSE", self.source_folder, os.path.join(self.package_folder, "licenses"))
        autotools = Autotools(self)
        autotools.install()

        rm(self, "*.la", os.path.join(self.package_folder, "lib"))
        rmdir(self, os.path.join(self.package_folder, "lib", "pkgconfig"))
        rmdir(self, os.path.join(self.package_folder, "share"))

        fix_apple_shared_install_name(self)

    def package_info(self):
        cbc = self.cpp_info.components["libcbc"]
        cbc.libs = ["CbcSolver", "Cbc"]
        cbc.includedirs = ["include/coin"]
        cbc.requires = [
            "coin-clp::osi-clp",
            "coin-utils::coin-utils",
            "coin-osi::coin-osi",
            "coin-cgl::coin-cgl",
        ]
        cbc.set_property("pkg_config_name", "cbc")

        if self.settings.os in ["Linux", "FreeBSD"] and self.options.parallel:
            cbc.system_libs.append("pthread")

        if self.settings.os == "Windows" and self.options.parallel:
            cbc.requires.append("pthreads4w::pthreads4w")

        osi_cbc = self.cpp_info.components["osi-cbc"]
        osi_cbc.libs = ["OsiCbc"]
        osi_cbc.requires = ["libcbc"]
        osi_cbc.set_property("pkg_config_name", "osi-cbc")
