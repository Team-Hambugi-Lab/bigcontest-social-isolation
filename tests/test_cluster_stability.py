"""시간대 패턴 군집(2단계)의 안정성 회귀 테스트.

초기 리포트는 "군집이 지역과 강하게 겹친다"고 서술했으나 ARI는 0.021로
전혀 겹치지 않았다. 검정 결과를 여기에 고정한다.
"""

import numpy as np
import pytest
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler

from src.data import regions
from src.features import sk_dong

SEED = 42


@pytest.fixture(scope="module")
def clustering():
    panel = sk_dong.build_space_panel()
    prof = panel.groupby("dong_cd", observed=True)[sk_dong.TIME_COLS].sum()
    share = prof.div(prof.sum(axis=1), axis=0)
    x = StandardScaler().fit_transform(share.values)
    region = np.array([regions.SGG_NAMES[d[:5]] for d in share.index])
    labels = KMeans(n_clusters=2, random_state=SEED, n_init=10).fit_predict(x)
    return x, region, labels, share.index


def test_k2_beats_permutation_null(clustering):
    """구조 없는 데이터에서는 이만한 실루엣이 나오지 않는다."""
    x, _, labels, _ = clustering
    observed = silhouette_score(x, labels)
    rng = np.random.default_rng(SEED)
    null = []
    for _ in range(50):
        xp = np.column_stack([rng.permutation(x[:, j]) for j in range(x.shape[1])])
        lab = KMeans(n_clusters=2, random_state=0, n_init=3).fit_predict(xp)
        null.append(silhouette_score(xp, lab))
    assert observed > np.quantile(null, 0.95) * 3


def test_cluster_is_not_region_partition(clustering):
    """군집은 강남/춘천 구분이 아니다. ARI가 0에 가깝다."""
    _, region, labels, _ = clustering
    assert adjusted_rand_score(region, labels) < 0.10


def test_bootstrap_stability_is_high(clustering):
    """동을 재표집해도 같은 분할이 재현된다."""
    x, _, labels, _ = clustering
    rng = np.random.default_rng(SEED)
    aris = []
    for b in range(60):
        idx = np.unique(rng.choice(len(x), size=len(x), replace=True))
        lab_b = KMeans(n_clusters=2, random_state=b, n_init=5).fit_predict(x[idx])
        aris.append(adjusted_rand_score(labels[idx], lab_b))
    assert np.mean(aris) > 0.75


def test_algorithms_agree(clustering):
    """KMeans·Ward·GMM이 거의 같은 분할을 준다."""
    x, _, labels, _ = clustering
    ward = AgglomerativeClustering(n_clusters=2, linkage="ward").fit_predict(x)
    gmm = GaussianMixture(n_components=2, random_state=SEED, n_init=10).fit_predict(x)
    assert adjusted_rand_score(labels, ward) > 0.85
    assert adjusted_rand_score(labels, gmm) > 0.85


def test_minority_cluster_membership(clustering):
    """소수 군집은 춘천 8개 + 강남 2개로 구성된다."""
    _, region, labels, index = clustering
    minor = np.bincount(labels).argmin()
    members = set(index[labels == minor])
    assert len(members) == 10
    assert {"11230580", "11230720"} <= members
    assert (region[labels == minor] == "강원 춘천시").sum() == 8
