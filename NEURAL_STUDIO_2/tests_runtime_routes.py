import tempfile
from pathlib import Path
import threading
import unittest
from unittest.mock import Mock
from providers_engine.runtime import RuntimeTransport
from providers_engine.transport import validate


class RuntimeRoutes(unittest.TestCase):
    def test_gemini_uses_exact_high_adapter_and_scope_guard(self):
        runtime=RuntimeTransport();runtime.gemini=Mock()
        runtime.gemini.run.return_value={'status':'COMPLETED','text':'fixture'}
        row=dict(route='gemini',model='gemini-3.8-flash-high',effort='high')
        validate(**{k:row[k] for k in ('route','model','effort')})
        with self.assertRaisesRegex(ValueError,'high'):validate('gemini',row['model'],'medium')
        self.assertTrue(runtime.supports('gemini','production'))
        with tempfile.TemporaryDirectory() as folder:
            runtime.run(row,{},Path(folder),None,threading.Event());runtime.gemini.run.assert_called_once()
            result=runtime.run(row,{'toolMode':'production'},Path(folder),None,threading.Event())
            self.assertFalse(result['execution_started']);self.assertEqual(runtime.gemini.run.call_count,1)
            runtime.run(row,{'toolMode':'production','productionScope':'fixture'},Path(folder),None,threading.Event())
            self.assertEqual(runtime.gemini.run.call_count,2)


if __name__=='__main__':unittest.main()
