--- eclipsis/ECLISPSIS-AI-main/Makefile	2026-08-05 02:41:41.000000000 +0000
+++ eclipsis_fixed/Makefile	2026-08-05 03:21:44.731682974 +0000
@@ -1,16 +1,16 @@
 run:
-    python run.py
+	python run.py
 
 test:
-    pytest -q
+	pytest -q
 
 lint:
-    ruff check .
+	ruff check .
 
 typecheck:
-    mypy src/
+	mypy src/
 
 start-api:
-    uvicorn api:app --reload
+	uvicorn api:app --reload
 ui:
 	python run.py