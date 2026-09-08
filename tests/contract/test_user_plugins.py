from videep.algorithms.contracts import AlgorithmRole
from videep.algorithms.loader import load_algorithm


def test_editable_plugins_load_with_independent_roles() -> None:
    references = {
        AlgorithmRole.PREPROCESS: "plugins.preprocess:Plugin",
        AlgorithmRole.INFERENCE: "plugins.inference:Plugin",
        AlgorithmRole.POSTPROCESS: "plugins.postprocess:Plugin",
    }
    loaded = {role: load_algorithm(reference, role) for role, reference in references.items()}
    assert set(loaded) == set(AlgorithmRole)
    assert len({type(component) for component in loaded.values()}) == 3
