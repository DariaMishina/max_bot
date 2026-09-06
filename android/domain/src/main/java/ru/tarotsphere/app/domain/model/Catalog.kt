package ru.tarotsphere.app.domain.model

data class CatalogPackage(
    val id: String,
    val name: String,
    val priceRub: Int,
    val isSubscription: Boolean,
)

data class Catalog(
    val packages: List<CatalogPackage>,
    val paymentMethods: List<String>,
)
