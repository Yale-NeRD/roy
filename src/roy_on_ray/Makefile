all:
	@python setup.py build_ext --inplace
	@mv roy_on_ray/*.so .
	@rm -rf roy_on_ray

clean:
	@rm -rf build
	@rm -rf *.so *.c
