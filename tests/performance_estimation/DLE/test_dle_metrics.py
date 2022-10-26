#  Author:   Niels Nuyttens  <niels@nannyml.com>
#
#  License: Apache Software License 2.0
import pandas as pd
import pytest

from nannyml.base import AbstractEstimator, AbstractEstimatorResult
from nannyml.datasets import load_synthetic_car_price_dataset
from nannyml.performance_estimation.direct_loss_estimation import DLE


class FakeEstimator(AbstractEstimator):
    def _fit(self, reference_data: pd.DataFrame, *args, **kwargs) -> AbstractEstimator:
        pass

    def _estimate(self, data: pd.DataFrame, *args, **kwargs) -> AbstractEstimatorResult:
        pass


@pytest.mark.parametrize(
    'calculator_opts, expected',
    [
        (
            {'chunk_size': 20000},
            pd.DataFrame(
                {
                    'key': ['[0:19999]', '[20000:39999]', '[40000:59999]'],
                    'estimated_mae': [845.9611134332384, 781.4926674835554, 711.0517135412116],
                    'estimated_mape': [0.23267452687056098, 0.24304465695708963, 0.25434522765463374],
                    'estimated_mse': [1122878.6557536805, 996772.391655789, 860754.7329283138],
                    'estimated_rmse': [1059.659688651824, 998.384891540226, 927.7686850332435],
                    'estimated_msle': [0.07129931251850186, 0.08237610554658686, 0.09424921080964306],
                    'estimated_rmsle': [0.2670193111340486, 0.2870123787340659, 0.30700034333798887],
                }
            ),
        ),
        (
            {'chunk_size': 20000, 'timestamp_column_name': 'timestamp'},
            pd.DataFrame(
                {
                    'key': ['[0:19999]', '[20000:39999]', '[40000:59999]'],
                    'estimated_mae': [845.9611134332384, 781.4926674835554, 711.0517135412116],
                    'estimated_mape': [0.23267452687056098, 0.24304465695708963, 0.25434522765463374],
                    'estimated_mse': [1122878.6557536805, 996772.391655789, 860754.7329283138],
                    'estimated_rmse': [1059.659688651824, 998.384891540226, 927.7686850332435],
                    'estimated_msle': [0.07129931251850186, 0.08237610554658686, 0.09424921080964306],
                    'estimated_rmsle': [0.2670193111340486, 0.2870123787340659, 0.30700034333798887],
                }
            ),
        ),
        (
            {'chunk_number': 4},
            pd.DataFrame(
                {
                    'key': ['[0:14999]', '[15000:29999]', '[30000:44999]', '[45000:59999]'],
                    'estimated_mae': [847.3424959557017, 845.7373344640564, 711.5439127244119, 713.3835827998372],
                    'estimated_mape': [
                        0.23214149556800917,
                        0.23284470158214202,
                        0.25471199464536814,
                        0.2537210235141931,
                    ],
                    'estimated_mse': [1128043.558035664, 1120912.7518854835, 859451.4065392805, 865466.657323283],
                    'estimated_rmse': [1062.093949721805, 1058.7316713339048, 927.0660205936148, 930.3046045910355],
                    'estimated_msle': [
                        0.07099665700945837,
                        0.07144067806672186,
                        0.09442423585275446,
                        0.09370460090404097,
                    ],
                    'estimated_rmsle': [
                        0.2664519788056722,
                        0.26728389039880773,
                        0.3072852678745834,
                        0.30611207245719824,
                    ],
                }
            ),
        ),
        (
            {'chunk_number': 4, 'timestamp_column_name': 'timestamp'},
            pd.DataFrame(
                {
                    'key': ['[0:14999]', '[15000:29999]', '[30000:44999]', '[45000:59999]'],
                    'estimated_mae': [847.3424959557017, 845.7373344640564, 711.5439127244119, 713.3835827998372],
                    'estimated_mape': [
                        0.23214149556800917,
                        0.23284470158214202,
                        0.25471199464536814,
                        0.2537210235141931,
                    ],
                    'estimated_mse': [1128043.558035664, 1120912.7518854835, 859451.4065392805, 865466.657323283],
                    'estimated_rmse': [1062.093949721805, 1058.7316713339048, 927.0660205936148, 930.3046045910355],
                    'estimated_msle': [
                        0.07099665700945837,
                        0.07144067806672186,
                        0.09442423585275446,
                        0.09370460090404097,
                    ],
                    'estimated_rmsle': [
                        0.2664519788056722,
                        0.26728389039880773,
                        0.3072852678745834,
                        0.30611207245719824,
                    ],
                }
            ),
        ),
        (
            {'chunk_period': 'M', 'timestamp_column_name': 'timestamp'},
            pd.DataFrame(
                {
                    'key': ['2017-02', '2017-03'],
                    'estimated_mae': [839.9892842078503, 711.6793261625646],
                    'estimated_mape': [0.2334885072120842, 0.25441754369504815],
                    'estimated_mse': [1111996.0629481985, 860567.8087450431],
                    'estimated_rmse': [1054.5122393543845, 927.6679409923807],
                    'estimated_msle': [0.07234480460729872, 0.09418692237490388],
                    'estimated_rmsle': [0.2689698953550354, 0.3068988797224647],
                }
            ),
        ),
        (
            {},
            pd.DataFrame(
                {
                    'key': [
                        '[0:5999]',
                        '[6000:11999]',
                        '[12000:17999]',
                        '[18000:23999]',
                        '[24000:29999]',
                        '[30000:35999]',
                        '[36000:41999]',
                        '[42000:47999]',
                        '[48000:53999]',
                        '[54000:59999]',
                    ],
                    'estimated_mae': [
                        849.5639685964373,
                        848.7184466434562,
                        842.7092353630159,
                        849.0077257199042,
                        842.7001997265812,
                        715.7915405144998,
                        714.4308784285377,
                        711.8195599307788,
                        714.5584926607276,
                        705.7182672760792,
                    ],
                    'estimated_mape': [
                        0.23107162545446974,
                        0.23273121873466127,
                        0.23346395434814515,
                        0.23156279696192553,
                        0.2336358973761762,
                        0.25298911958498194,
                        0.2547138215609582,
                        0.253774827282499,
                        0.2534991075167855,
                        0.25610566945367863,
                    ],
                    'estimated_mse': [
                        1139377.7053649914,
                        1129419.217327195,
                        1112040.535613815,
                        1128981.1043172355,
                        1112572.2121796315,
                        865825.3950750288,
                        865532.7479281372,
                        862284.1323365847,
                        869065.8827812723,
                        849587.0015353857,
                    ],
                    'estimated_rmse': [
                        1067.4163692603704,
                        1062.741368973277,
                        1054.533325985393,
                        1062.5352249771465,
                        1054.7853867871092,
                        930.4973912241929,
                        930.3401248619438,
                        928.5925545343257,
                        932.2370314363576,
                        921.7304386507943,
                    ],
                    'estimated_msle': [
                        0.0706372455894371,
                        0.07116430399895682,
                        0.07171993662227429,
                        0.07056145753021863,
                        0.07201039394956373,
                        0.09311525247406541,
                        0.09410921276805023,
                        0.09402118738701887,
                        0.09370361672238206,
                        0.09537282254047202,
                    ],
                    'estimated_rmsle': [
                        0.2657766836828187,
                        0.26676638468697067,
                        0.26780578153257684,
                        0.26563406696095776,
                        0.26834752458251543,
                        0.30514791900661126,
                        0.3067722490187961,
                        0.3066287452066731,
                        0.30611046490177696,
                        0.30882490595881673,
                    ],
                }
            ),
        ),
        (
            {'timestamp_column_name': 'timestamp'},
            pd.DataFrame(
                {
                    'key': [
                        '[0:5999]',
                        '[6000:11999]',
                        '[12000:17999]',
                        '[18000:23999]',
                        '[24000:29999]',
                        '[30000:35999]',
                        '[36000:41999]',
                        '[42000:47999]',
                        '[48000:53999]',
                        '[54000:59999]',
                    ],
                    'estimated_mae': [
                        849.5639685964373,
                        848.7184466434562,
                        842.7092353630159,
                        849.0077257199042,
                        842.7001997265812,
                        715.7915405144998,
                        714.4308784285377,
                        711.8195599307788,
                        714.5584926607276,
                        705.7182672760792,
                    ],
                    'estimated_mape': [
                        0.23107162545446974,
                        0.23273121873466127,
                        0.23346395434814515,
                        0.23156279696192553,
                        0.2336358973761762,
                        0.25298911958498194,
                        0.2547138215609582,
                        0.253774827282499,
                        0.2534991075167855,
                        0.25610566945367863,
                    ],
                    'estimated_mse': [
                        1139377.7053649914,
                        1129419.217327195,
                        1112040.535613815,
                        1128981.1043172355,
                        1112572.2121796315,
                        865825.3950750288,
                        865532.7479281372,
                        862284.1323365847,
                        869065.8827812723,
                        849587.0015353857,
                    ],
                    'estimated_rmse': [
                        1067.4163692603704,
                        1062.741368973277,
                        1054.533325985393,
                        1062.5352249771465,
                        1054.7853867871092,
                        930.4973912241929,
                        930.3401248619438,
                        928.5925545343257,
                        932.2370314363576,
                        921.7304386507943,
                    ],
                    'estimated_msle': [
                        0.0706372455894371,
                        0.07116430399895682,
                        0.07171993662227429,
                        0.07056145753021863,
                        0.07201039394956373,
                        0.09311525247406541,
                        0.09410921276805023,
                        0.09402118738701887,
                        0.09370361672238206,
                        0.09537282254047202,
                    ],
                    'estimated_rmsle': [
                        0.2657766836828187,
                        0.26676638468697067,
                        0.26780578153257684,
                        0.26563406696095776,
                        0.26834752458251543,
                        0.30514791900661126,
                        0.3067722490187961,
                        0.3066287452066731,
                        0.30611046490177696,
                        0.30882490595881673,
                    ],
                }
            ),
        ),
    ],
    ids=[
        'size_based_without_timestamp',
        'size_based_with_timestamp',
        'count_based_without_timestamp',
        'count_based_with_timestamp',
        'period_based_with_timestamp',
        'default_without_timestamp',
        'default_with_timestamp',
    ],
)
def test_dle_for_regression_with_timestamps(calculator_opts, expected):
    ref_df, ana_df, _ = load_synthetic_car_price_dataset()
    dle = DLE(
        feature_column_names=[col for col in ref_df.columns if col not in ['timestamp', 'y_true', 'y_pred']],
        y_pred='y_pred',
        y_true='y_true',
        metrics=['mae', 'mape', 'mse', 'rmse', 'msle', 'rmsle'],
        **calculator_opts,
    ).fit(ref_df)
    result = dle.estimate(ana_df)
    sut = result.filter(period='analysis').to_df()[
        [('chunk', 'key')] + [(metric.column_name, 'value') for metric in result.metrics]
    ]
    sut.columns = [
        'key',
        'estimated_mae',
        'estimated_mape',
        'estimated_mse',
        'estimated_rmse',
        'estimated_msle',
        'estimated_rmsle',
    ]

    pd.testing.assert_frame_equal(expected, sut)
