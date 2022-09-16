from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd
from plotly.graph_objs import Figure
from sqlmodel import Field, Relationship, Session, SQLModel, create_engine

from nannyml.exceptions import WriterException
from nannyml.io.base import Writer


class Model(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    # runs: List["Run"] = Relationship(back_populates="model")


class Run(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    # model_id: int = Field(default=None, foreign_key="model.id")
    # model: Model = Relationship(back_populates="runs")
    metrics: List["Metric"] = Relationship(back_populates="run")
    execution_timestamp: datetime = Field(default=datetime.now())


class Metric(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(default=None, foreign_key="run.id")
    run: Run = Relationship(back_populates="metrics")
    name: str
    value: float


class DatabaseWriter(Writer):
    def __init__(self, connection_string: str, **connection_opts):
        super().__init__()
        self.connection_string = connection_string
        self._engine = create_engine(url=connection_string, **connection_opts)
        try:
            SQLModel.metadata.create_all(self._engine)
        except Exception as exc:
            raise WriterException(f"could not create DatabaseWriter: {exc}")

    def _write(self, data: pd.DataFrame, plots: Dict[str, Figure], **kwargs):

        print(data)

        run = Run()
        metrics = [
            Metric(name=f'estimated_{metric}', value=row[f'estimated_{metric}'], run=run)
            for metric in ['mae', 'mape', 'mse', 'msle', 'rmse', 'rmsle']
            for _, row in data.iterrows()
        ]

        with Session(self._engine) as session:
            session.add(run)
            session.add_all(metrics)
            session.commit()
