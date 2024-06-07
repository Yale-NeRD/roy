#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <vector>
#include <memory>

namespace py = pybind11;

class Roylist {
public:
    Roylist(const std::vector<py::object>& ref_list, size_t chunk_size, size_t len) 
        : chunk_ref_list(ref_list), chunk_size(chunk_size), len(len) {
        if (ref_list.empty()) {
            throw std::invalid_argument("Value cannot be None");
        }
        if (chunk_size <= 0) {
            throw std::invalid_argument("Chunk size must be greater than 0");
        }

        if (!is_ray_initialized()) {
            throw std::invalid_argument("Ray must be initialized");
        }
        // setup checklist
        chunk_list = std::make_unique<std::unique_ptr<py::object[]>[]>(ref_list.size());
    }

    py::object get_item(size_t idx) {
        if (idx >= len) {
            throw std::out_of_range("Index out of range");
        }

        size_t chunk_idx = idx / chunk_size;
        if (!chunk_list[chunk_idx]) {
            auto chunk = get_from_ray(chunk_ref_list[chunk_idx]);
            std::unique_ptr<py::object[]> chunk_array(new py::object[chunk.size()]);
            for (size_t i = 0; i < chunk.size(); ++i) {
                chunk_array[i] = chunk[i];
            }
            chunk_list[chunk_idx] = std::move(chunk_array);
        }

        size_t element_idx = idx % chunk_size;
        return chunk_list[chunk_idx][element_idx];
    }

    // void set_chunk_list(const std::vector<std::shared_ptr<std::vector<py::object>>>& chunk_list) {
    //     this->chunk_list = chunk_list;
    // }

    // Custom serialization (pickle) methods
    // py::dict __getstate__() const {
    //     py::dict state;
    //     state["chunk_ref_list"] = chunk_ref_list;
    //     state["chunk_size"] = chunk_size;
    //     state["len"] = len;
    //     return state;
    // }

    // static std::unique_ptr<Roylist> __setstate__(py::dict state) {
    //     if (!state.contains("chunk_ref_list") || !state.contains("chunk_size") || !state.contains("len") || !state.contains("num_chunks")) {
    //         throw std::runtime_error("State dictionary missing required keys");
    //     }

    //     std::vector<py::object> chunk_ref_list = state["chunk_ref_list"].cast<std::vector<py::object>>();
    //     size_t chunk_size = state["chunk_size"].cast<size_t>();
    //     size_t len = state["len"].cast<size_t>();

    //     // Create the object using the standard constructor
    //     auto obj = Roylist(chunk_ref_list, chunk_size, len);
    //     obj.set_chunk_list(state["chunk_list"].cast<std::vector<std::shared_ptr<std::vector<py::object>>>>());
    //     return std::make_unique<Roylist>(obj);
    // }    

private:
    std::vector<py::object> chunk_ref_list;
    std::unique_ptr<std::unique_ptr<py::object[]>[]> chunk_list;
    size_t chunk_size;
    size_t len;

    bool is_ray_initialized() const {
        py::object ray = py::module::import("ray");
        return ray.attr("is_initialized")().cast<bool>();
    }

    py::list get_from_ray(const py::object& ref) const {
        py::object ray = py::module::import("ray");
        py::object result = ray.attr("get")(ref);
        return result.cast<py::list>();
    }
};

PYBIND11_MODULE(roylist, m) {
    py::class_<Roylist>(m, "Roylist")
        .def(py::init<const std::vector<py::object>&, size_t, size_t>())
        .def("__getitem__", &Roylist::get_item);
        // .def("__getstate__", &Roylist::__getstate__);
        // .def("__setstate__", &Roylist::__setstate__);
}