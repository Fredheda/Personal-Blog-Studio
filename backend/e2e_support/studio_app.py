"""The real studio API on Azurite, for the browser tests (frontend/e2e).

Not shipped: no Dockerfile copies this directory. Azurite is the public
development account (`UseDevelopmentStorage=true`), so no key is written down.
"""

import os

from azure.core.exceptions import ResourceExistsError

from blog_core import layout
from blog_core.azure_store import AzureBlobStore
from studio_api.app import create_app
from studio_api.posts import PostService

store = AzureBlobStore.from_connection_string("UseDevelopmentStorage=true")
for name in (layout.DRAFTS, layout.PUBLISHED):
    try:
        store.service.create_container(name)
    except ResourceExistsError:
        pass

# The origin guard is on, with the web app's origin: a browser POST carries it.
app = create_app(PostService(store), allowed_origins=[os.environ["E2E_WEB_ORIGIN"]])
