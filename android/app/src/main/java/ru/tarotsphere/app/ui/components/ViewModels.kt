package ru.tarotsphere.app.ui.components

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider

fun <VM : ViewModel> simpleFactory(create: () -> VM): ViewModelProvider.Factory =
    object : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T = create() as T
    }

fun Exception.userMessage(): String =
    (this as? ru.tarotsphere.app.domain.model.AppFailure)?.message
        ?: "Не удалось загрузить данные. Попробуйте снова."
