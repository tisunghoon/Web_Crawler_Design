from hypothesis import settings

settings.register_profile("default", max_examples=100, deadline=None)
settings.load_profile("default")
