"""Shared constants and configuration defaults for DevLens."""

VERSION = "2.0.0"

DEFAULT_IGNORED_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "dist",
    "build",
    "target",
    "coverage",
    ".next",
    ".pytest_cache",
    ".mypy_cache",
    ".tox",
    "egg-info",
    ".idea",
    ".vscode",
    "vendor",
}

# Extensions treated as "source" for the purposes of code statistics.
SOURCE_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rs", ".c", ".h",
    ".cpp", ".hpp", ".cc", ".cs", ".rb", ".php", ".swift", ".kt", ".kts",
    ".scala", ".sh", ".bash", ".sql", ".html", ".css", ".scss", ".vue",
    ".m", ".mm", ".pl", ".lua", ".r", ".jl",
}

# Extensions we never treat as text (binary by default), regardless of sniffing.
KNOWN_BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".pdf",
    ".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".rar",
    ".exe", ".dll", ".so", ".dylib", ".bin", ".class", ".jar", ".war",
    ".pyc", ".pyo", ".o", ".a", ".db", ".sqlite", ".sqlite3", ".woff",
    ".woff2", ".ttf", ".eot", ".mp3", ".mp4", ".mov", ".avi", ".wasm",
}

COMMENT_PREFIXES_BY_EXT = {
    ".py": ("#",),
    ".sh": ("#",),
    ".bash": ("#",),
    ".rb": ("#",),
    ".yml": ("#",),
    ".yaml": ("#",),
    ".js": ("//",),
    ".jsx": ("//",),
    ".ts": ("//",),
    ".tsx": ("//",),
    ".java": ("//",),
    ".go": ("//",),
    ".rs": ("//",),
    ".c": ("//",),
    ".h": ("//",),
    ".cpp": ("//",),
    ".hpp": ("//",),
    ".cc": ("//",),
    ".cs": ("//",),
    ".swift": ("//",),
    ".kt": ("//",),
    ".scala": ("//",),
    ".php": ("//", "#"),
    ".sql": ("--",),
    ".lua": ("--",),
}

DEFAULT_MAX_FILE_SIZE_MB = 10
LONG_LINE_THRESHOLD = 200
HASH_CHUNK_SIZE = 65536
DUPLICATE_HASH_MAX_BYTES = 50 * 1024 * 1024  # 50 MB; larger files are skipped

MARKER_PATTERNS = {
    "todo_count": ("TODO",),
    "fixme_count": ("FIXME",),
    "xxx_count": ("XXX",),
}

DEPENDENCY_MANIFESTS = {
    "python": ["requirements.txt", "pyproject.toml", "setup.py", "setup.cfg", "Pipfile"],
    "node": ["package.json", "package-lock.json"],
    "rust": ["Cargo.toml", "Cargo.lock"],
    "go": ["go.mod", "go.sum"],
    "java": ["pom.xml", "build.gradle"],
}

PROJECT_TYPE_MARKERS = {
    "Python": ["pyproject.toml", "requirements.txt", "setup.py", "setup.cfg", "Pipfile"],
    "Node.js": ["package.json"],
    "Rust": ["Cargo.toml"],
    "Go": ["go.mod"],
    "Java (Maven)": ["pom.xml"],
    "Java (Gradle)": ["build.gradle", "build.gradle.kts"],
    "C/C++": ["CMakeLists.txt", "Makefile"],
}

HYGIENE_EXPECTED_FILES = {
    "README": ["README.md", "README.rst", "README.txt", "README"],
    "LICENSE": ["LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING"],
    "gitignore": [".gitignore"],
}

CI_CONFIG_PATHS = [
    ".github/workflows",
    ".gitlab-ci.yml",
    ".travis.yml",
    "azure-pipelines.yml",
    "Jenkinsfile",
    ".circleci/config.yml",
]

DEFAULT_SCORE_WEIGHTS = {
    "security": 0.30,
    "code_health": 0.25,
    "documentation": 0.15,
    "dependencies": 0.15,
    "hygiene": 0.15,
}
