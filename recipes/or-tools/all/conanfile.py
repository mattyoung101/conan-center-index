from conan import ConanFile
from conan.errors import ConanInvalidConfiguration
from conan.tools.build import check_min_cppstd
from conan.tools.cmake import CMake, CMakeDeps, CMakeToolchain, cmake_layout
from conan.tools.files import apply_conandata_patches, copy, export_conandata_patches, get, rm, rmdir
from conan.tools.microsoft import is_msvc, is_msvc_static_runtime
import os


required_conan_version = ">=2.0.9"

# docker run --rm -v $(pwd):/usr/src/project -it conanio/gcc11-ubuntu16.04:2.2.2 bash


class PackageConan(ConanFile):
    name = "or-tools"
    description = " Google's Operations Research tools"
    license = "Apache-2.0"
    url = "https://github.com/google/or-tools"
    homepage = "https://developers.google.com/optimization"
    # no "conan" and project name in topics. Use topics from the upstream listed on GH
    topics = ("optimization", "linear-programming", "operations-research",
              "combinatorial-optimization", "or-tools")
    # package_type should usually be "library", "shared-library" or "static-library"
    package_type = "library"
    settings = "os", "arch", "compiler", "build_type"
    options = {
        "shared": [True, False],
        "fPIC": [True, False],
    }
    default_options = {
        "shared": False,
        "fPIC": True,
    }
    implements = ["auto_shared_fpic"]

    def export_sources(self):
        export_conandata_patches(self)

    def layout(self):
        cmake_layout(self, src_folder="src")

    def requirements(self):
        self.requires("zlib/1.3.1")
        self.requires("bzip2/1.0.8")
        # unresolvable version conflict on Abseil between re2 and protobuf, (20240116.1 vs 20240116.2)
        # since it's just one minor version off, force this version
        self.requires("abseil/20240116.1", force=True)
        self.requires("protobuf/[>=4.25.3]")
        self.requires("coin-utils/2.11.9")
        self.requires("coin-osi/0.108.7")
        self.requires("coin-clp/1.17.7")
        self.requires("coin-cgl/0.60.7")
        self.requires("highs/1.11.0")
        self.requires("scip/9.2.3")
        self.requires("benchmark/1.9.4")
        self.requires("soplex/7.1.5")
        self.requires("eigen/3.4.0")
        self.requires("re2/20240301")
        self.requires("coin-cbc/2.10.5")

    def build_requirements(self):
        self.tool_requires("cmake/[>=3.20 <4]")

    def validate(self):
        check_min_cppstd(self, 14)

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)
        apply_conandata_patches(self)

    def generate(self):
        tc = CMakeToolchain(self)
        tc.variables["BUILD_TESTING"] = "OFF"
        tc.variables["BUILD_SHARED_LIBS"] = "ON"
        # CBC is not built for Conan yet
        tc.variables["USE_COINOR"] = "FALSE"
        if is_msvc(self):
            tc.cache_variables["USE_MSVC_RUNTIME_LIBRARY_DLL"] = not is_msvc_static_runtime(self)
        tc.generate()

        deps = CMakeDeps(self)
        deps.generate()

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def package(self):
        copy(self, "LICENSE", self.source_folder, os.path.join(self.package_folder, "licenses"))
        cmake = CMake(self)
        cmake.install()

        # Some files extensions and folders are not allowed. Please, read the FAQs to get informed.
        # Consider disabling these at first to verify that the package_info() output matches the info exported by the project.
        rmdir(self, os.path.join(self.package_folder, "lib", "pkgconfig"))
        rmdir(self, os.path.join(self.package_folder, "lib", "cmake"))
        rmdir(self, os.path.join(self.package_folder, "share"))
        rm(self, "*.pdb", self.package_folder, recursive=True)

    def package_info(self):
        # library name to be packaged
        self.cpp_info.libs = ["package_lib"]
        # if package has an official FindPACKAGE.cmake listed in https://cmake.org/cmake/help/latest/manual/cmake-modules.7.html#find-modules
        # examples: bzip2, freetype, gdal, icu, libcurl, libjpeg, libpng, libtiff, openssl, sqlite3, zlib...
        self.cpp_info.set_property("cmake_module_file_name", "PACKAGE")
        self.cpp_info.set_property("cmake_module_target_name", "PACKAGE::PACKAGE")
        # if package provides a CMake config file (package-config.cmake or packageConfig.cmake, with package::package target, usually installed in <prefix>/lib/cmake/<package>/)
        self.cpp_info.set_property("cmake_file_name", "package")
        self.cpp_info.set_property("cmake_target_name", "package::package")
        # if package provides a pkgconfig file (package.pc, usually installed in <prefix>/lib/pkgconfig/)
        self.cpp_info.set_property("pkg_config_name", "package")

        # If they are needed on Linux, m, pthread and dl are usually needed on FreeBSD too
        if self.settings.os in ["Linux", "FreeBSD"]:
            self.cpp_info.system_libs.append("m")
            self.cpp_info.system_libs.append("pthread")
            self.cpp_info.system_libs.append("dl")
