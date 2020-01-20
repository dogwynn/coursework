def hash_from_content(content: Union[bytes, str]):
    return hashlib.md5(
        content if type(content) is bytes else content.encode('utf-8')
    ).hexdigest()

def compute_file_hash(file: IdResourceEndpoint):
    return hash_from_content(
        requests.get(file.data['url']).content
    )

_FILE_HASHES_KEY = 'file-hashes'
def _get_file_hashes(api: Api):
    hashes = get_data(api, _FILE_HASHES_KEY)
    if hashes is None:
        hashes = {}
        _set_file_hashes(api, hashes)
    return hashes

def _set_file_hashes(api: Api, hashes: dict):
    set_data(api, _FILE_HASHES_KEY, hashes)

def get_file_hash(file: IdResourceEndpoint):
    hashes = _get_file_hashes(file.api)
    uuid = file.data['uuid']
    return hashes.get(uuid)

def set_file_hash(file: IdResourceEndpoint, file_hash: str):
    hashes = _get_file_hashes(file.api)
    uuid = file.data['uuid']
    hashes[uuid] = file_hash
    _set_file_hashes(file, hashes)

def set_file_hash_from_path(file: IdResourceEndpoint, path: str):
    file_hash = hash_from_content(path.read_bytes())
    set_file_hash(file, file_hash)

def set_file_hashes(files: List[IdResourceEndpoint], hashes: List[str]):
    if files and hashes and len(files) == len(hashes):
        hash_db = _get_file_hashes(files[0].api)
        for f, h in zip(files, hashes):
            uuid = f.data['uuid']
            hash_db[uuid] = h
        _set_file_hashes(files[0].api, hash_db)
        return True
    return False

def set_hashes_for_courses(courses: List[IdResourceEndpoint]):
    return pipe(
        courses,
        pmap(files),
        map(lambda file_eps: pipe(
            file_eps,
            pmap(lambda f: (f, compute_file_hash(f))),
            tuple
        )),
        filter(None),
        map(lambda hashes: set_file_hashes(*zip(*hashes))),
        tuple
    )

