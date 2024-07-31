all:
	@python setup.py build_ext --inplace
	@mv roytypes/*.so .
	@rm -rf roytypes

clean:
	@rm -rf build
	@rm -rf *.so *.c
